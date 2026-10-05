`Model.objects.filter(name__icontains="x")` becomes a `Lookup` object when you call `.filter()`. The SQL string is only built when the QuerySet is evaluated. On PostgreSQL the WHERE clause comes out as `UPPER("app_model"."name"::text) LIKE UPPER(%s)`, with the parameter `'%x%'`.

## Phase 1: QuerySet → Query (when `.filter()` is called)

1. **`QuerySet.filter`**, `django/db/models/query.py:1724`, calls `_filter_or_exclude(False, args, kwargs)` at line 1730.
2. **`_filter_or_exclude`**, `query.py:1740`, clones the QuerySet (`self._chain()`, line 1743) and calls `_filter_or_exclude_inplace` on the clone.
3. **`_filter_or_exclude_inplace`**, `query.py:1751`, runs `self._query.add_q(Q(*args, **kwargs))` at line 1758.
   - `Q.__init__` (`django/db/models/query_utils.py:55`) turns the kwargs into sorted tuple children: `[("name__icontains", "x")]` (line 58).
4. **`Query.add_q`**, `django/db/models/sql/query.py:1674`, calls `_add_q` at line 1691 and adds the resulting clause to `self.where` with AND (line 1693).
5. **`Query._add_q`**, `sql/query.py:1703`, creates a `WhereNode` (line 1718) and calls `build_filter(child, ...)` for each child (line 1723).

## Phase 2: `Query.build_filter` (`sql/query.py:1499`)

- **Line 1559:** unpacks `arg, value = ("name__icontains", "x")`.
- **Line 1562:** calls **`solve_lookup_type`** (`sql/query.py:1344`).
  - It splits on `__` to get `["name", "icontains"]` (line 1348).
  - `names_to_path` (`sql/query.py:1786`) resolves `name` through `opts.get_field(name)` (line 1812). `icontains` doesn't match a field, so it is left over as a lookup part.
  - It returns `lookups=["icontains"]`, `parts=["name"]`.
- **Line 1571:** `resolve_lookup_value` (`sql/query.py:1323`). `"x"` is a plain value, so it is returned unchanged.
- **Lines 1584–1594:** `get_initial_alias()` (line 1113) and `setup_joins(["name"], ...)` (line 1902). No joins are needed for a local field.
- **Line 1610:** `trim_joins` (line 2019).
- **Line 1622:** `_get_col` (line 453) calls `target.get_col(alias, field)`, which gives a `Col(alias, name_field)`.
- **Line 1624:** `condition = self.build_lookup(["icontains"], col, "x")`.
- **Line 1626:** wraps the condition in `WhereNode([condition], connector=AND)`.

## Phase 3: Lookup resolution

- **`Query.build_lookup`**, `sql/query.py:1415`:
  - `*transforms, lookup_name = ["icontains"]` (line 1425). There are no transforms.
  - **Line 1431:** `lookup_class = lhs.get_lookup("icontains")`.
    - `RegisterLookupMixin.get_lookup` (`query_utils.py:347`) first tries `_get_lookup` on the `Col` (line 328). That fails, so it falls back to `self.output_field.get_lookup(...)` (line 351), i.e. the CharField.
    - `Field` subclasses `RegisterLookupMixin` (`django/db/models/fields/__init__.py:129`).
    - `get_lookups` → `get_class_lookups` (`query_utils.py:332`) merges `class_lookups` across the MRO. That dict holds `IContains` because of the `@Field.register_lookup` decorator.
  - **Line 1441:** `lookup = lookup_class(lhs, rhs)` instantiates `IContains(col, "x")`.
  - Lines 1444–1456 are the None and Oracle-empty-string checks. They don't apply here.
- **`Lookup.__init__`**, `django/db/models/lookups.py:34`, calls `get_prep_lookup()` (line 95). Because `PatternLookup.prepare_rhs = False` (line 586), `"x"` is returned as is.

## Phase 4: The IContains class hierarchy (`django/db/models/lookups.py`)

| Class | Line | Role |
|---|---|---|
| `IContains(Contains)` | 631 | `lookup_name = "icontains"`, registered on `Field` |
| `Contains(PatternLookup)` | 626 | `lookup_name = "contains"` |
| `PatternLookup(BuiltinLookup)` | 584 | `param_pattern = "%%%s%%"`, `prepare_rhs = False`, overrides `get_rhs_op` (588) and `process_rhs` (603) |
| `BuiltinLookup(Lookup)` | 234 | `process_lhs` (235), `as_sql` (243), `get_rhs_op` (250) |
| `Lookup(Expression)` | 29 | base `process_lhs` (107), `process_rhs` (117), `get_db_prep_lookup` (104) |

## Phase 5: SQL compilation (when the QuerySet is evaluated)

1. **`ModelIterable.__iter__`**, `query.py:134`:
   - `query.get_compiler(using=db)` (line 137) calls `Query.get_compiler` (`sql/query.py:370`), which returns `connection.ops.compiler("SQLCompiler")` (`backends/base/operations.py:406`).
   - `compiler.execute_sql(...)` is called at line 141.
2. **`SQLCompiler.execute_sql`**, `django/db/models/sql/compiler.py:1619`, calls `self.as_sql()` (around line 1636), then `cursor.execute(sql, params)` (around line 1649).
3. **`SQLCompiler.as_sql`**, `compiler.py:776`:
   - `pre_sql_setup` (line 83) splits `query.where` into `self.where`, `having` and `qualify` (line 91).
   - `self.compile(self.where)` runs at line 815.
4. **`SQLCompiler.compile`**, `compiler.py:593`, first looks for `as_postgresql` on the node. `IContains` has none, so it falls back to `node.as_sql(self, connection)`.
5. **`WhereNode.as_sql`**, `django/db/models/sql/where.py:116`, calls `compiler.compile(child)` for each child and joins the results with `AND`. It then reaches the `IContains` node.
6. **`BuiltinLookup.as_sql`**, `lookups.py:243`:
   - **LHS:** `BuiltinLookup.process_lhs` (235) → `Lookup.process_lhs` (107) → `compiler.compile(col)` → `Col.as_sql` (`django/db/models/expressions.py:1366`) gives `"app_model"."name"`.
     - It then applies `connection.ops.lookup_cast("icontains", "CharField")`.
     - That is **`postgresql/operations.py:158`**: `"%s::text"` (line 175), wrapped as `UPPER(%s)` because the lookup is case-insensitive (lines 178–179).
     - Result: `UPPER("app_model"."name"::text)`.
   - **RHS:** `PatternLookup.process_rhs` (603) → `Lookup.process_rhs` (117). `"x"` has no `as_sql`, so it uses `get_db_prep_lookup` (line 139), which returns `("%s", ("x",))`.
     - `is_simple_lookup` is True (`rhs_is_direct_value`, line 141), so the parameter goes through `connection.ops.prep_for_like_query` (`backends/base/operations.py:537`). That escapes `\`, `%` and `_`.
     - `features.pattern_lookup_needs_param_pattern` is True (`backends/base/features.py:436`), so `param_pattern` turns the parameter into `'%x%'`.
   - **Operator:** `PatternLookup.get_rhs_op` (588) is a simple lookup, so it calls `BuiltinLookup.get_rhs_op` (250), which returns `connection.operators["icontains"] % "%s"`.
     - That is **`postgresql/base.py:148`**: `"LIKE UPPER(%s)"`.
     - If the RHS were an expression, the code would use `pattern_ops["icontains"]` (`base.py:174`) with `pattern_esc` instead.
   - `as_sql` returns `"%s %s" % (lhs_sql, rhs_sql)` together with the combined params.

## Result

```sql
SELECT ... FROM "app_model" WHERE UPPER("app_model"."name"::text) LIKE UPPER(%s)
-- params: ('%x%',)
```

`SQLCompiler.as_sql` then puts together SELECT, FROM and WHERE, and `execute_sql` passes the SQL and parameters to the psycopg cursor.