Here is the full path for `Model.objects.filter(name__icontains="x")` on PostgreSQL, where `name` is a `CharField`. It has two phases: building the `WhereNode` happens when you call `.filter()`, and turning it into SQL happens only when the QuerySet is evaluated.

## Phase 1 – Building the filter (lazy, at `.filter()` time)

**1. QuerySet API** (`django/db/models/query.py`)
- `QuerySet.filter` at `query.py:1724` calls `_filter_or_exclude(False, args, kwargs)` at `query.py:1730`.
- `_filter_or_exclude` at `query.py:1740` clones the QuerySet with `_chain()` (`query.py:1743`), then calls `clone._filter_or_exclude_inplace(...)` at `query.py:1748`.
- `_filter_or_exclude_inplace` at `query.py:1751` wraps the kwargs in `Q(name__icontains="x")` and calls `self._query.add_q(...)` at `query.py:1758`.
- The `Q` constructor at `django/db/models/query_utils.py:55` stores the children as sorted `(key, value)` tuples, here `("name__icontains", "x")` (`query_utils.py:58`).

**2. Query.add_q / _add_q** (`django/db/models/sql/query.py`)
- `add_q` at `query.py:1674` calls `_add_q` at `query.py:1692`, adds the result to `self.where` with AND at `query.py:1694`, then demotes joins.
- `_add_q` at `query.py:1703` creates a `WhereNode` at `query.py:1719`. For each child it calls `build_filter` at `query.py:1724` and adds the returned clause at `query.py:1737`.

**3. Query.build_filter** at `query.py:1499`
- The child is a tuple, not a `Q` or an expression, so it is unpacked: `arg, value = filter_expr` at `query.py:1559`.
- `solve_lookup_type("name__icontains")` runs at `query.py:1562`. The method is at `query.py:1344`:
  - It splits the string on `__` (`query.py:1348`).
  - It checks annotations first (`query.py:1349-1357`).
  - `names_to_path` (`query.py:1358`) resolves `name` to a field and leaves `["icontains"]` as the lookup parts.
  - It returns `lookups=["icontains"]` and `parts=["name"]` (`query.py:1365`).
- `resolve_lookup_value` at `query.py:1571` leaves the plain string `"x"` unchanged.
- `get_initial_alias()` at `query.py:1584` returns the base table alias.
- `setup_joins(["name"], ...)` at `query.py:1588` (defined at `query.py:1902`) creates no joins, because this is a local field.
- `trim_joins` runs at `query.py:1610`.
- `col = self._get_col(targets[0], join_info.final_field, alias)` at `query.py:1622` builds a `Col(alias, CharField)` (`_get_col` is at `query.py:453`).
- `condition = self.build_lookup(["icontains"], col, "x")` at `query.py:1624`.
- The condition is wrapped in `WhereNode([condition], connector=AND)` at `query.py:1626`. It isn't negated, so no extra `IS NOT NULL` clause is added.

**4. Lookup resolution: Query.build_lookup** at `query.py:1415`
- `*transforms, lookup_name = ["icontains"]` at `query.py:1425`. There are no transforms, so `try_transform` (`query.py:1461`) is skipped.
- `lookup_class = lhs.get_lookup("icontains")` at `query.py:1430`:
  - `Col` inherits `BaseExpression.get_lookup` (`django/db/models/expressions.py:403`), which delegates to its `output_field`, the `CharField`.
  - `Field` is a `RegisterLookupMixin` (`django/db/models/fields/__init__.py:129`). `RegisterLookupMixin.get_lookup` (`query_utils.py:347`) calls `_get_lookup` (`query_utils.py:328`), which looks the name up in the merged `class_lookups` along the MRO (`get_class_lookups`, `query_utils.py:331-336`).
  - `icontains` is in there because `@Field.register_lookup` decorates `IContains` at `django/db/models/lookups.py:630`.
- `lookup = IContains(col, "x")` at `query.py:1440`.
- The None check (`query.py:1443`) and the Oracle empty-string check (`query.py:1452`) don't apply here.

**5. The IContains lookup itself** (`django/db/models/lookups.py`)
- `class IContains(Contains)` at `lookups.py:631` sets `lookup_name = "icontains"`.
- `Contains(PatternLookup)` is at `lookups.py:626`.
- `PatternLookup(BuiltinLookup)` at `lookups.py:584` sets `param_pattern = "%%%s%%"` and `prepare_rhs = False` (`lookups.py:585-586`).
- `BuiltinLookup(Lookup)` is at `lookups.py:234`, and `Lookup(Expression)` at `lookups.py:29`.
- `Lookup.__init__` at `lookups.py:34` calls `get_prep_lookup()` (`lookups.py:89`). Because `prepare_rhs` is False, it returns `"x"` unchanged (`lookups.py:90-91`).

## Phase 2 – Compiling to SQL (at evaluation time)

**6. Execution entry point**
- Iterating the QuerySet triggers `_fetch_all`, which runs `ModelIterable.__iter__` (`query.py:134`).
- That calls `query.get_compiler(using=db)` at `query.py:137` (`Query.get_compiler` is at `sql/query.py:370`), then `compiler.execute_sql(...)` at `query.py:141`.
- `SQLCompiler.execute_sql` at `django/db/models/sql/compiler.py:1619` calls `self.as_sql()`, then `cursor.execute(sql, params)` at `compiler.py:1649`.

**7. SQLCompiler.as_sql** at `compiler.py:776`
- The WHERE clause is built at `compiler.py:815` with `self.compile(self.where)`.
- `SQLCompiler.compile` at `compiler.py:593` checks for a vendor-specific `as_postgresql` method (`compiler.py:594`) and otherwise calls `node.as_sql(self, connection)` (`compiler.py:598`).

**8. WhereNode.as_sql** at `django/db/models/sql/where.py:116`
- It calls `compiler.compile(child)` for each child (`where.py:151`) and joins the results with `" AND "` (`where.py:177-178`).
- The one child here is the `IContains` lookup, which has no `as_postgresql`, so its `as_sql` runs.

**9. BuiltinLookup.as_sql** at `lookups.py:243`
- **LHS:** `BuiltinLookup.process_lhs` at `lookups.py:235`:
  - `Lookup.process_lhs` (`lookups.py:107`) calls `compiler.compile(col)`, which runs `Col.as_sql` (`expressions.py:1366`) and produces `"app_model"."name"`.
  - It then applies `connection.ops.lookup_cast("icontains", "CharField")`. The PostgreSQL version is at `django/db/backends/postgresql/operations.py:158`: it adds `%s::text` (`operations.py:175`), then wraps that in `UPPER(...)` (`operations.py:178-179`).
  - Result: `UPPER("app_model"."name"::text)`.
- **RHS:** `PatternLookup.process_rhs` at `lookups.py:603`:
  - `Lookup.process_rhs` (`lookups.py:117`) gets a plain value with no `as_sql`, so it calls `get_db_prep_lookup` (`lookups.py:139`, defined at `lookups.py:104`), which returns `("%s", ("x",))`.
  - `is_simple_lookup` (`lookups.py:619`) is true, so it escapes the value with `connection.ops.prep_for_like_query("x")` (`django/db/backends/base/operations.py:537`), which escapes `\`, `%` and `_`.
  - `pattern_lookup_needs_param_pattern` is True by default (`django/db/backends/base/features.py:436`), so it wraps the value with `param_pattern`. The parameter becomes `"%x%"` (`lookups.py:612-615`).
- **Operator:** `PatternLookup.get_rhs_op` at `lookups.py:588`:
  - For a simple lookup it falls through to `BuiltinLookup.get_rhs_op` (`lookups.py:250`), which uses `connection.operators["icontains"]`.
  - On PostgreSQL that is `"LIKE UPPER(%s)"` (`django/db/backends/postgresql/base.py:148`).
  - If the right-hand side were an expression such as `F()`, it would use `pattern_ops["icontains"]` with `pattern_esc` instead (`postgresql/base.py:169-174`).
- `as_sql` then combines the pieces as `"%s %s" % (lhs_sql, rhs_sql)` (`lookups.py:248`).

## Final result

```sql
SELECT ... FROM "app_model" WHERE UPPER("app_model"."name"::text) LIKE UPPER(%s)
-- params: ('%x%',)
```

The driver (psycopg) binds the parameter at `compiler.py:1649`.