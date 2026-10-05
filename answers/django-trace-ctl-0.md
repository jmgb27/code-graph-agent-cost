Here is the path from the `.filter()` call to the final SQL on PostgreSQL. All paths are relative to `django/db/`.

## 1. QuerySet layer (runs when `.filter()` is called)

1. `Model.objects.filter(...)`: the Manager passes the call to the QuerySet through generated proxy methods (`models/manager.py:83-86`, `_get_queryset_methods` / `create_method`).
2. `QuerySet.filter` (`models/query.py:1724`) calls `_filter_or_exclude(False, args, kwargs)` (`models/query.py:1740`).
3. `_filter_or_exclude` clones the queryset with `_chain()`. It then calls `_filter_or_exclude_inplace` (`models/query.py:1751`), which wraps the kwargs as `Q(name__icontains="x")` and calls `self._query.add_q(...)` (`models/query.py:1759`).
   - If the filter was deferred, `QuerySet.query` (`models/query.py:396`) applies it later.

## 2. Query building: `sql/query.py`

4. **`Query.add_q`** (`models/sql/query.py:1674`) records which joins are currently INNER and calls `_add_q`. It then does `self.where.add(clause, AND)` (`:1694`) and runs `demote_joins`.
5. **`Query._add_q`** (`:1703`) creates a `WhereNode` for the Q's connector and a `JoinPromoter`. It calls `build_filter(child, ...)` for each child tuple `("name__icontains", "x")` (`:1719`).
6. **`Query.build_filter`** (`:1499`):
   - It unpacks `arg, value = filter_expr` (`:1560`).
   - **`solve_lookup_type("name__icontains")`** (`:1344`) splits the string on `__`. It checks annotations first, then calls **`names_to_path`** (`:1786`), which resolves `name` to the `CharField` and returns the leftover parts. The result is `lookups=["icontains"]`, `parts=["name"]`.
   - `resolve_lookup_value("x", ...)` (`:1323`): a plain string passes through unchanged.
   - `get_initial_alias()` (`:1113`) returns the base table alias.
   - **`setup_joins(["name"], opts, alias)`** (`:1902`) finds no relation, so no JOINs are added. `trim_joins` (`:2019`) returns the target field and alias.
   - `_get_col(targets[0], final_field, alias)` (`:453`) calls `field.get_col(alias)`, which returns a `Col(alias, name_field)`.
   - **`build_lookup(["icontains"], col, "x")`** (`:1621`) builds the condition, which is then wrapped as `WhereNode([condition], connector=AND)` (`:1623`).

## 3. Lookup resolution

7. **`Query.build_lookup`** (`models/sql/query.py:1415`):
   - `*transforms, lookup_name = ["icontains"]`: there are no transforms, so `try_transform` (`:1461`) is skipped.
   - `lookup_class = lhs.get_lookup("icontains")` (`:1430`).
   - `lookup_class(lhs, rhs)` instantiates the lookup. The `None` check and Oracle empty-string checks don't apply here.
8. **`RegisterLookupMixin.get_lookup`** (`models/query_utils.py:347`):
   - `Col` has no lookup of its own, so it falls back to `self.output_field.get_lookup(...)`, i.e. the `CharField`.
   - `_get_lookup` (`:328`) then calls `get_lookups()`, which merges `class_lookups` along the MRO (`get_class_lookups`, `:333`).
   - `IContains` is in that registry because it is registered on `Field` with `@Field.register_lookup` (`models/lookups.py:630`).

## 4. The IContains lookup: `models/lookups.py`

9. The class hierarchy is `IContains(Contains)` (`:631`, `lookup_name = "icontains"`) → `Contains(PatternLookup)` (`:626`) → `PatternLookup(BuiltinLookup)` (`:584`) → `BuiltinLookup(Lookup)` (`:234`) → `Lookup(Expression)` (`:29`).
10. `Lookup.__init__` (`:35`) calls `get_prep_lookup()` (`:89`). `PatternLookup.prepare_rhs = False` (`:586`), so `"x"` is returned unchanged and `Field.get_prep_value` is not called. `get_prep_lhs` keeps the `Col`.

## 5. SQL compilation (when the queryset is evaluated)

11. Iteration triggers the query. `QuerySet._fetch_all` (`models/query.py:2327`) calls `ModelIterable.__iter__` (`:134`), which calls `query.get_compiler(using=db)` (`models/sql/query.py:370`).
    - `connection.ops.compiler("SQLCompiler")` (`backends/base/operations.py:406`) imports from `compiler_module`.
    - For PostgreSQL that module is `django.db.backends.postgresql.compiler` (`backends/postgresql/operations.py:28`). It only overrides `SQLInsertCompiler` (`backends/postgresql/compiler.py:28`), so the SELECT path uses the generic `SQLCompiler`.
12. **`SQLCompiler.execute_sql`** (`models/sql/compiler.py:1619`) calls `self.as_sql()`.
13. **`SQLCompiler.as_sql`** (`:776`) runs `pre_sql_setup` (`:83`) and `get_from_clause`. It then calls **`self.compile(self.where)`** (`:814-815`).
14. **`SQLCompiler.compile`** (`:593`) dispatches to `as_<vendor>` (`as_postgresql`) if the node defines one, and otherwise to `node.as_sql(self, connection)`.
15. **`WhereNode.as_sql`** (`models/sql/where.py:116`) calls `compiler.compile(child)` for each child (`:151`) and joins the results with AND. The nested WhereNode compiles the same way until it reaches the `IContains` lookup.
16. **`BuiltinLookup.as_sql`** (`models/lookups.py:243`):
    - **LHS: `BuiltinLookup.process_lhs`** (`:235`)
      - `Lookup.process_lhs` (`:107`) calls `compiler.compile(col)`, which calls `Col.as_sql` (`models/expressions.py:1366`) and returns `"app_model"."name"`.
      - It then wraps the result with `connection.ops.lookup_cast("icontains", "CharField")`, which is `backends/postgresql/operations.py:158`:
        - `%s::text` for text lookups (`:162-175`), or `HOST(%s)` for IP fields.
        - `UPPER(...)` for case-insensitive lookups (`:177-179`).
      - Result: `UPPER("app_model"."name"::text)`.
    - **RHS: `PatternLookup.process_rhs`** (`:603`)
      - `Lookup.process_rhs` (`:117`) sees that `"x"` has no `as_sql`, so it calls `get_db_prep_lookup` (`:104`) and gets `("%s", ("x",))`.
      - `is_simple_lookup` is True (`:618`), so it calls `connection.ops.prep_for_like_query("x")` (`backends/base/operations.py:537`). This escapes `\`, `%` and `_`.
      - Because `features.pattern_lookup_needs_param_pattern` is True (`backends/base/features.py:436`), it applies `param_pattern = "%%%s%%"` (`:585`). The parameter becomes `"%x%"`.
    - **Operator: `PatternLookup.get_rhs_op`** (`:588`)
      - A simple lookup falls through to `BuiltinLookup.get_rhs_op` (`:250`), which uses `connection.operators["icontains"]` = `"LIKE UPPER(%s)"` (`backends/postgresql/base.py:148`).
      - If the RHS were an expression or column, it would use `pattern_ops["icontains"]` (`base.py:174`) with the `pattern_esc` REPLACE chain (`base.py:169`), giving `LIKE '%%' || UPPER(...) || '%%'`.
    - The pieces are joined as `"%s %s" % (lhs_sql, rhs_sql)`.
17. `execute_sql` then runs `cursor.execute(sql, params)` (`models/sql/compiler.py:1649`).

## Final result (PostgreSQL)

```sql
SELECT ... FROM "app_model"
WHERE UPPER("app_model"."name"::text) LIKE UPPER(%s)
-- params: ('%x%',)
```

The `%s` placeholder is bound to `'%x%'` by the psycopg driver.