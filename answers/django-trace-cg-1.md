`Model.objects.filter(name__icontains="x")` produces `WHERE UPPER("app_model"."name"::text) LIKE UPPER(%s)` on PostgreSQL, with `['%x%']` passed separately as the parameter. The trace below comes from reading the source.

## 1. QuerySet API → Query

| Step | Location |
|---|---|
| `Model.objects.filter` is a generated manager method that calls `self.get_queryset().filter(...)` | `django/db/models/manager.py:84-89` |
| `QuerySet.filter` → `_filter_or_exclude(False, args, kwargs)` | `django/db/models/query.py:1724-1730` |
| `_filter_or_exclude` clones the queryset (`_chain()`), then calls `_filter_or_exclude_inplace` | `django/db/models/query.py:1740-1749` |
| This wraps the kwargs as `Q(name__icontains="x")` and calls `self._query.add_q(...)` | `django/db/models/query.py:1751-1758` |

## 2. `Query.add_q` → `_add_q` → `build_filter`

- `Query.add_q` (`django/db/models/sql/query.py:1674`) calls `_add_q`, then ANDs the result into `self.where` (`:1692-1694`) and demotes joins where it can.
- `Query._add_q` (`:1703`) creates a `WhereNode` for the Q object. For each child tuple `("name__icontains", "x")` it calls `build_filter` (`:1723-1737`).
- `Query.build_filter` (`:1499`):
  - Splits the tuple into `arg, value` (`:1559`).
  - **`solve_lookup_type(arg)`** (`:1562` → `:1344`) splits on `__` into `["name", "icontains"]`. It first checks annotations using `refs_expression` (`django/db/models/query_utils.py:469`). If there's no match, it calls `names_to_path` (`sql/query.py:1786`). That resolves `name` to the `CharField` and returns the leftover names as `lookup_parts = ["icontains"]` and `field_parts = ["name"]`.
  - `resolve_lookup_value` (`:1571` → `:1323`) leaves the plain string `"x"` as it is.
  - `setup_joins(parts, opts, alias)` (`:1588` → `:1902`) runs from the base table alias (`get_initial_alias`, `:1113`). No joins are needed for a local field.
  - `trim_joins` (`:1610` → `:2019`) runs next, then `_get_col` (`:1622` → `:453`) builds a `Col(alias, name_field)`.
  - **`build_lookup(["icontains"], col, "x")`** (`:1624`), then wraps the result in `WhereNode([condition], AND)` (`:1626`). The branch at `:1631+` only adds `IS NOT NULL` handling for negated filters, so it doesn't apply here.

## 3. Lookup resolution

- `Query.build_lookup` (`sql/query.py:1415`):
  - Splits the list into `*transforms, lookup_name`. There are no transforms here.
  - Calls `lhs.get_lookup("icontains")` (`:1430`).
  - If nothing is found, it falls back to `try_transform` plus `exact` (`:1431-1438`, `:1461`).
  - Instantiates `lookup_class(lhs, rhs)` (`:1440`).
  - Checks for a `None` rhs and applies Oracle's empty-string rule (`:1443-1457`).
- `RegisterLookupMixin.get_lookup` (`django/db/models/query_utils.py:347`) calls `_get_lookup` (`:328`), which calls `get_lookups()`. That merges `class_lookups` across the MRO (`:331-344`), so `CharField` inherits lookups registered on `Field`. If the lookup isn't found, it delegates to `output_field.get_lookup` (`:351-352`).
- Registration: `@Field.register_lookup` on `IContains` (`django/db/models/lookups.py:630`) goes through `register_class_lookup` (`query_utils.py:384-391`), which stores `Field.class_lookups["icontains"] = IContains`.
- `Lookup.__init__` (`lookups.py:34`) calls `get_prep_lookup()` (`:89`). `PatternLookup.prepare_rhs = False` (`:586`), so the rhs stays the raw `"x"`.

## 4. The `IContains` class hierarchy

```
IContains (lookups.py:631, lookup_name="icontains")
 └ Contains (:626)
    └ PatternLookup (:584, param_pattern="%%%s%%", prepare_rhs=False)
       └ BuiltinLookup (:234)
          └ Lookup (:29) → Expression
```

`IContains` has no `as_postgresql` of its own, so compilation falls through to `BuiltinLookup.as_sql`.

## 5. SQL compilation

1. **Execution entry point:** iterating the queryset runs `ModelIterable.__iter__` (`django/db/models/query.py:134`). That calls `query.get_compiler(using=db)` (`:137` → `sql/query.py:370-377`), which uses `connection.ops.compiler(...)`.
   - PostgreSQL's `compiler_module` is `django.db.backends.postgresql.compiler` (`backends/postgresql/operations.py:28`). That module re-exports the base `SQLCompiler` (`backends/postgresql/compiler.py:1`) and overrides only the insert compiler, so SELECTs use `django/db/models/sql/compiler.py:43`.
2. `SQLCompiler.execute_sql` (`compiler.py:1619`) calls `self.as_sql()` (`:1636`) and later `cursor.execute(sql, params)` (`:1649`).
3. `SQLCompiler.as_sql` (`:776`) calls `pre_sql_setup` (`:787` → `:83`). That splits `query.where` into where/having/qualify (`:91`). It then runs `self.compile(self.where)` (`:815`).
4. **`SQLCompiler.compile`** (`:593-599`) looks for an `as_<vendor>` method first, i.e. `as_postgresql`. If there isn't one, it calls `node.as_sql(compiler, connection)`.
5. `WhereNode.as_sql` (`sql/where.py:116`) calls `compiler.compile(child)` for each child (`:151`) and joins the pieces with AND. The child is the `IContains` lookup.
6. **`BuiltinLookup.as_sql`** (`lookups.py:243-248`):
   - **LHS:** `BuiltinLookup.process_lhs` (`:235`) calls `Lookup.process_lhs` (`:107`), which calls `compiler.compile(col)`. That reaches `Col.as_sql` (`expressions.py:1366`), which returns `"app_model"."name"`.
     - It then applies `connection.ops.lookup_cast("icontains", "CharField")` (`:239`).
     - The PostgreSQL version (`backends/postgresql/operations.py:158-181`) returns `%s::text` for text lookups (`:175`), then wraps it as `UPPER(%s::text)` for case-insensitive lookups (`:178-179`).
     - Result: `UPPER("app_model"."name"::text)`.
   - **RHS:** `PatternLookup.process_rhs` (`:603`) calls `Lookup.process_rhs` (`:117`). The rhs is a plain value with no `as_sql`, so that goes through `get_db_prep_lookup` (`:139` → `:104`), which returns `("%s", ("x",))`.
     - Because `is_simple_lookup` is true (`:619-622`), it escapes the value with `prep_for_like_query` (`backends/base/operations.py:537-539`; this escapes `\`, `%` and `_`).
     - `pattern_lookup_needs_param_pattern` is true (`backends/base/features.py:436`), so `param_pattern` turns the value into `'%x%'` (`lookups.py:612-615`).
   - **Operator:** `PatternLookup.get_rhs_op` (`:588`). For a simple lookup it calls `BuiltinLookup.get_rhs_op` (`:250-251`), which returns `connection.operators["icontains"] % rhs`.
     - The PostgreSQL value is `"LIKE UPPER(%s)"` (`backends/postgresql/base.py:148`).
     - If the rhs is an expression or F() instead, it uses `pattern_ops["icontains"]` with `pattern_esc`, giving `LIKE '%%' || UPPER(REPLACE(...)) || '%%'` (`base.py:169-174`, `lookups.py:592-598`).

## Final output

```sql
SELECT ... FROM "app_model" WHERE UPPER("app_model"."name"::text) LIKE UPPER(%s)
-- params: ('%x%',)
```

psycopg binds the parameter at `compiler.py:1649`.