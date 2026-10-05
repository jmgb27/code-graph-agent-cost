I traced the whole path from `filter()` to the final PostgreSQL SQL; the answer follows. I found these references with codegraph plus a few targeted greps and reads, and I didn't edit anything.

**Result on PostgreSQL:** `Model.objects.filter(name__icontains="x")` compiles to `... WHERE UPPER("app_model"."name"::text) LIKE UPPER(%s)` with the parameter `'%x%'`.

## 1. From the QuerySet to the Query
- `Model.objects.filter` is a manager method copied from `QuerySet` by `BaseManager._get_queryset_methods` (`django/db/models/manager.py:83`).
- `QuerySet.filter` (`django/db/models/query.py:1724`) calls `_filter_or_exclude(False, args, kwargs)` (`query.py:1740`). That clones the queryset with `_chain()` and calls `_filter_or_exclude_inplace` (`query.py:1751`).
- `_filter_or_exclude_inplace` wraps the kwargs as `Q(name__icontains="x")` and calls `self._query.add_q(...)` (`query.py:1758`).
- `Query.add_q` (`django/db/models/sql/query.py:1674`) calls `_add_q` (`query.py:1692`). It then does `self.where.add(clause, AND)` (`query.py:1694`) and demotes joins where it can.
- `Query._add_q` (`query.py:1703`) builds a `WhereNode` for the Q's connector. It calls `build_filter` for each child, here the tuple `("name__icontains", "x")` (`query.py:1724`).

## 2. `Query.build_filter` (`query.py:1499`)
- The input is a tuple, not a `Q` or an expression, so it gets unpacked at `query.py:1559`.
- `solve_lookup_type(arg)` runs at `query.py:1562`, defined at `query.py:1344`:
  - It splits the string on `LOOKUP_SEP` into `["name", "icontains"]` (`query.py:1348`).
  - It calls `names_to_path` (`query.py:1358`, defined at `query.py:1786`). That resolves `name` to a model field and returns `["icontains"]` as the leftover lookup parts.
  - It returns `lookups=["icontains"]`, `parts=["name"]`, `reffed_expression=False`.
- `resolve_lookup_value` (`query.py:1571`) leaves the plain string `"x"` as it is.
- `setup_joins(parts, ...)` (`query.py:1588`, defined at `query.py:1902`) and `trim_joins` (`query.py:1610`) resolve to the base table alias. No joins are needed for a local field.
- `self._get_col(...)` (`query.py:1622`, defined at `query.py:453`) creates `Col(alias, CharField name)`.
- `self.build_lookup(["icontains"], col, "x")` runs at `query.py:1624`. The resulting condition is wrapped in `WhereNode([condition], AND)` (`query.py:1626`).

## 3. Lookup resolution: `Query.build_lookup` (`query.py:1415`)
- `*transforms, lookup_name = lookups` (`query.py:1425`) leaves no transforms, and `lookup_name` is `"icontains"`.
- `lhs.get_lookup("icontains")` runs at `query.py:1430`. `Col` inherits from `RegisterLookupMixin`:
  - `RegisterLookupMixin.get_lookup` (`django/db/models/query_utils.py:347`) calls `_get_lookup` (`query_utils.py:328`), then `get_lookups()`.
  - `get_lookups` is the `class_or_instance_method` defined at `query_utils.py:344`. It uses `get_class_lookups`, which merges the `class_lookups` dicts across the MRO (`query_utils.py:332`).
  - `Col` has no lookup of its own, so the call falls through to `self.output_field.get_lookup(...)` (`query_utils.py:351-352`), which is the `CharField`.
  - `IContains` is registered on `Field` by the `@Field.register_lookup` decorator (`django/db/models/lookups.py:630`), so the field returns the `IContains` class.
- `lookup_class(lhs, rhs)` runs at `query.py:1440`, which is `Lookup.__init__` (`lookups.py:34`):
  - `get_prep_lookup()` (`lookups.py:36`, `lookups.py:89`) returns the value unchanged because `PatternLookup.prepare_rhs = False` (`lookups.py:586`).
  - `get_prep_lhs()` (`lookups.py:37`) keeps the `Col`, and there are no bilateral transforms.
- The `None` and Oracle empty-string checks (`query.py:1443-1457`) don't apply, so the `IContains` instance is returned (`query.py:1459`).

## 4. The IContains lookup class hierarchy (`django/db/models/lookups.py`)
- `class IContains(Contains)` sets `lookup_name = "icontains"` (`lookups.py:631-632`).
- `class Contains(PatternLookup)` sets `lookup_name = "contains"` (`lookups.py:626`).
- `class PatternLookup(BuiltinLookup)` (`lookups.py:584`) sets `param_pattern = "%%%s%%"` (`lookups.py:585`).
- `class BuiltinLookup(Lookup)` (`lookups.py:234`), whose base is `class Lookup(Expression)` (`lookups.py:29`).

## 5. SQL compilation
- `str(qs.query)` or iteration reaches `ModelIterable.__iter__` (`query.py:131`). That calls `compiler.execute_sql(...)` (`query.py:141`) on the compiler from `Query.get_compiler` (`sql/query.py:370`).
- `SQLCompiler.execute_sql` (`django/db/models/sql/compiler.py:1619`) calls `self.as_sql()` (`compiler.py:1636`), then `cursor.execute(sql, params)` (`compiler.py:1649`).
- `SQLCompiler.as_sql` (`compiler.py:776`):
  - It runs `pre_sql_setup`, which splits `where` into where/having/qualify (`compiler.py:91`).
  - It then calls `self.compile(self.where)` (`compiler.py:815`).
- `SQLCompiler.compile` (`compiler.py:593`) first looks for a vendor-specific method named `as_postgresql` (`compiler.py:594`). None exists for `WhereNode` or `IContains`, so it falls back to `node.as_sql(...)`.
- `WhereNode.as_sql` (`django/db/models/sql/where.py:116`) calls `compiler.compile(child)` for each child (`where.py:151`) and joins the results with `AND` (`where.py:177-178`).
- `BuiltinLookup.as_sql` (`lookups.py:243`) produces the condition from three pieces.

**Left-hand side:** `BuiltinLookup.process_lhs` (`lookups.py:235`)
- It calls `Lookup.process_lhs` (`lookups.py:107`), which runs `compiler.compile(Col)`.
- `Col.as_sql` (`django/db/models/expressions.py:1366`) produces `"app_model"."name"`, quoting names through `quote_name_unless_alias` (`compiler.py:582`).
- It then applies `connection.ops.lookup_cast("icontains", "CharField")` (`lookups.py:239`). The PostgreSQL version is `DatabaseOperations.lookup_cast` (`django/db/backends/postgresql/operations.py:158`):
  - it adds a `::text` cast (`operations.py:175`);
  - it wraps the result in `UPPER(...)` (`operations.py:178-179`).
- Result: `UPPER("app_model"."name"::text)`.

**Right-hand side:** `PatternLookup.process_rhs` (`lookups.py:603`)
- It calls `Lookup.process_rhs` (`lookups.py:117`). `"x"` has no `as_sql`, so `get_db_prep_lookup` returns `("%s", ("x",))` (`lookups.py:104-105`).
- `is_simple_lookup` is true (`lookups.py:619`), so `connection.ops.prep_for_like_query("x")` escapes `\`, `%` and `_` (`django/db/backends/base/operations.py:537`).
- `pattern_lookup_needs_param_pattern` defaults to `True` (`django/db/backends/base/features.py:436`), so the value becomes `"%%%s%%" % "x"`, which is `"%x%"` (`lookups.py:613-614`).

**Operator:** `PatternLookup.get_rhs_op` (`lookups.py:588`)
- For a simple lookup it calls `BuiltinLookup.get_rhs_op` (`lookups.py:250`), which returns `connection.operators["icontains"] % rhs`.
- The PostgreSQL operator is `"icontains": "LIKE UPPER(%s)"` (`django/db/backends/postgresql/base.py:148`).
- If the right-hand side is an expression such as `F()`, it uses `pattern_ops["icontains"]` instead, which is `LIKE '%%' || UPPER({}) || '%%'` (`postgresql/base.py:174`), with `pattern_esc` from `postgresql/base.py:169`.

`BuiltinLookup.as_sql` then returns `"%s %s" % (lhs_sql, rhs_sql)` (`lookups.py:248`), which gives the WHERE clause shown at the top.