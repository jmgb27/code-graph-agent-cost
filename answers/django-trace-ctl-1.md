Here is the full path for `Model.objects.filter(name__icontains="x")` on PostgreSQL. All paths are relative to `django/db/`.

## 1. QuerySet layer: build a `Q` and hand it to `Query`
- `QuerySet.filter()` at `models/query.py:1724` calls `_filter_or_exclude(False, args, kwargs)` at `models/query.py:1740`, which clones the queryset with `_chain()`.
- `_filter_or_exclude_inplace()` at `models/query.py:1751` wraps the kwargs as `Q(name__icontains="x")` and calls `self._query.add_q(...)` (`models/query.py:1757`).

## 2. `Query.add_q`, `_add_q`, `build_filter`
- `Query.add_q()` at `models/sql/query.py:1674` calls `_add_q()` and ANDs the returned clause into `self.where` (`:1693-1695`). It then demotes joins, which does nothing here because there are no joins.
- `Query._add_q()` at `models/sql/query.py:1703` creates a `WhereNode(connector=AND)` and a `JoinPromoter`. For each child, here the tuple `("name__icontains", "x")`, it calls `build_filter()` (`:1720`).
- `Query.build_filter()` at `models/sql/query.py:1499`:
  - It unpacks `arg, value = filter_expr` (`:1558`).
  - It calls `solve_lookup_type("name__icontains")` (`:1561`), covered in step 3.
  - It calls `resolve_lookup_value("x", ...)` (`:1570`, defined at `:1323`). A plain string has no `resolve_expression`, so the value comes back unchanged.
  - It calls `get_initial_alias()` (`:1582`, defined at `:1113`), which registers the base table alias.
  - It calls `setup_joins(["name"], opts, alias)` (`:1586`, defined at `:1902`). `name` is a local field, so the path is empty and no joins are added. It returns a `JoinInfo` (`:2017`).
  - `trim_joins()` (`:1606`, defined at `:2019`) returns the target field and the alias.
  - `_get_col()` (`:1618`, defined at `:453`) calls `Field.get_col()` (`models/fields/__init__.py:575`). This returns `Col(alias, CharField name)`, usually the `cached_col` (`:593`).
  - `build_lookup(["icontains"], col, "x")` (`:1620`) builds the lookup, covered in step 3.
  - The lookup is wrapped as `WhereNode([condition], connector=AND)` (`:1622`). The negation and IS NULL branches are skipped because this is not an exclude.

## 3. Lookup resolution
- `solve_lookup_type()` at `models/sql/query.py:1344` splits the string on `__` into `["name", "icontains"]`. With no annotations, it calls `names_to_path()` (`:1360`, defined at `:1786`).
  - `names_to_path()` resolves `"name"` through `opts.get_field()` (`:1812`).
  - `"icontains"` is not a field, so it is returned as a leftover lookup part.
  - The result is `lookup_parts=["icontains"]`, `field_parts=["name"]`.
- `build_lookup()` at `models/sql/query.py:1415`:
  - `*transforms, lookup_name = ["icontains"]` (`:1425`). There are no transforms.
  - `lhs.get_lookup("icontains")` (`:1430`):
    - `Col` inherits `BaseExpression.get_lookup()` (`models/expressions.py:403`), which delegates to `output_field.get_lookup()`.
    - That is `RegisterLookupMixin.get_lookup()` (`models/query_utils.py:347`), then `_get_lookup()` (`:328`), then `get_lookups()` / `get_class_lookups()` (`:332`).
    - `get_class_lookups()` merges the `class_lookups` dicts across the field's MRO, so `CharField` inherits what is registered on `Field`.
  - `IContains` is registered on `Field` by the `@Field.register_lookup` decorator (`models/lookups.py:630-632`).
  - `lookup_class(lhs, rhs)` runs `Lookup.__init__` (`models/lookups.py:34`):
    - `get_prep_lookup()` (`:89`) returns `"x"` unchanged because `PatternLookup.prepare_rhs = False` (`:586`).
    - There are no bilateral transforms.
  - The None and Oracle empty-string checks (`models/sql/query.py:1443-1457`) don't apply, so the `IContains` instance is returned (`:1459`).

## 4. The `IContains` class hierarchy
`IContains` (`models/lookups.py:631`) extends `Contains` (`:626`), which extends `PatternLookup` (`:584`), then `BuiltinLookup` (`:234`), then `Lookup` (`:29`).

- `IContains` only sets `lookup_name = "icontains"`.
- It inherits `param_pattern = "%%%s%%"` from `PatternLookup` (`:585`), which becomes `%x%` after `%` formatting.

## 5. Compilation to SQL
- Evaluating the queryset:
  1. `QuerySet._fetch_all()` (`models/query.py:2327`) runs `ModelIterable.__iter__()` (`:134`).
  2. That gets a compiler with `query.get_compiler()` (`:137`, defined at `models/sql/query.py:370`).
  3. It calls `SQLCompiler.execute_sql()` (`models/sql/compiler.py:1619`), which calls `self.as_sql()` (`:1636`) and then `cursor.execute(sql, params)` (`:1649`).
- In `SQLCompiler.as_sql()` (`models/sql/compiler.py:776`):
  - `pre_sql_setup()` (`:83`) splits `where` into where, having and qualify (`:91`).
  - It calls `self.compile(self.where)` (`:815`) and emits `"WHERE %s"` (`:914`).
- `SQLCompiler.compile()` (`models/sql/compiler.py:593`) looks for an `as_postgresql` method first (`:594`). Neither `WhereNode` nor `IContains` defines one, so it falls back to `node.as_sql()`.
- `WhereNode.as_sql()` (`models/sql/where.py:116`) compiles each child (`:151`) and joins the results with `" AND "`. With a single child, no parentheses are added (`:177-188`). The top-level node reaches the inner node, which reaches the `IContains` lookup.
- `BuiltinLookup.as_sql()` (`models/lookups.py:243`):
  - **LHS:** `BuiltinLookup.process_lhs()` (`:235`) calls `Lookup.process_lhs()` (`:107`), which calls `compiler.compile(col)`.
    - `Col.as_sql()` (`models/expressions.py:1366`) produces `"app_model"."name"`.
    - It then applies `connection.ops.lookup_cast("icontains", "CharField")` (`models/lookups.py:239`), which is the PostgreSQL `DatabaseOperations.lookup_cast()` (`backends/postgresql/operations.py:158`).
    - That function adds `%s::text` (`:175`) and wraps it in `UPPER(...)` (`:178-179`), giving `UPPER("app_model"."name"::text)`.
  - **RHS:** `PatternLookup.process_rhs()` (`models/lookups.py:603`) calls `Lookup.process_rhs()` (`:117`).
    - The value has no `as_sql`, so it goes to `get_db_prep_lookup()` (`:139`, then `:104`), which returns `("%s", ("x",))`.
    - `is_simple_lookup` is true (`:619-622`), so it escapes the value with `connection.ops.prep_for_like_query()` (`backends/base/operations.py:537`), which escapes `\`, `%` and `_`.
    - `features.pattern_lookup_needs_param_pattern` is `True` by default (`backends/base/features.py:436`), so `param_pattern` is applied (`models/lookups.py:613-614`) and the param becomes `"%x%"`.
  - **Operator:** `PatternLookup.get_rhs_op()` (`models/lookups.py:588`) sees a simple lookup and falls through to `BuiltinLookup.get_rhs_op()` (`:250`).
    - That looks up `connection.operators["icontains"]`, which is `"LIKE UPPER(%s)"` (`backends/postgresql/base.py:148`).
    - The `pattern_ops` / `pattern_esc` path (`backends/postgresql/base.py:169-179`) is only used when the RHS is an expression, for example `F()`.
  - The lookup returns `"%s %s" % (lhs_sql, rhs_sql)` (`models/lookups.py:248`).

## Result
```sql
SELECT ... FROM "app_model" WHERE UPPER("app_model"."name"::text) LIKE UPPER(%s)
-- params: ('%x%',)
```
psycopg fills in the `%s` placeholder at `cursor.execute` (`models/sql/compiler.py:1649`).