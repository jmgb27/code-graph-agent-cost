I'll trace this through the Django ORM for you.

## Execution Flow: `Model.objects.filter(name__icontains="x")`

**1. QuerySet.filter() entry point:**
- **django/db/models/query.py:1724** — `QuerySet.filter()` calls `_filter_or_exclude(False, ...)`
- **django/db/models/query.py:1740-1758** — `_filter_or_exclude_inplace()` wraps arguments in Q object and calls `self._query.add_q(Q(name__icontains="x"))`

**2. Query.add_q() processes the Q object:**
- **django/db/models/sql/query.py:1674** — `Query.add_q()` delegates to `_add_q()`
- **django/db/models/sql/query.py:1703-1734** — `_add_q()` iterates Q children and calls `build_filter()` for each

**3. Query.build_filter() — Lookup resolution:**
- **django/db/models/sql/query.py:1499-1624** — `build_filter()` is the core method
- **django/db/models/sql/query.py:1562** — Calls `solve_lookup_type("name__icontains")` to split the field path from the lookup name
- **django/db/models/sql/query.py:1344-1365** — `solve_lookup_type()` splits on `__` and calls `names_to_path()`, returning `(["icontains"], ["name"], field)`
- **django/db/models/sql/query.py:1624** — Calls `build_lookup(["icontains"], col, "x")`

**4. Query.build_lookup() — Lookup class instantiation:**
- **django/db/models/sql/query.py:1415-1459** — `build_lookup()` extracts lookup name from list
- **django/db/models/sql/query.py:1430** — Calls `lhs.get_lookup("icontains")` (where lhs is a Col expression)
- **django/db/models/expressions.py:403** — Expression.`get_lookup()` delegates to `self.output_field.get_lookup()`
- **django/db/models/query_utils.py:347-355** — Field/RegisterLookupMixin.`get_lookup()` calls `_get_lookup()` which gets from `get_lookups()`
- **django/db/models/query_utils.py:328-329** — `_get_lookup()` retrieves from registered lookup dictionary

**5. Lookup registration — IContains lookup class:**
- **django/db/models/lookups.py:631-632** — `@Field.register_lookup` decorator registers `IContains` class
- **django/db/models/lookups.py:626-632** — Class hierarchy: `IContains` extends `Contains` extends `PatternLookup` extends `BuiltinLookup` extends `Lookup`
- **django/db/models/sql/query.py:1440** — Lookup is instantiated: `lookup = IContains(col, "x")`

**6. SQL compilation — Lookup.as_sql():**
- **django/db/models/sql/compiler.py:593-598** — `SQLCompiler.compile()` calls `lookup.as_sql()`
- **django/db/models/lookups.py:243-248** — `BuiltinLookup.as_sql()` calls:
  - `process_lhs()` — processes left side (column reference)
  - `process_rhs()` — processes right side (value)
  - `get_rhs_op()` — gets the SQL operator
  
**7. PatternLookup specifics:**
- **django/db/models/lookups.py:603-616** — `PatternLookup.process_rhs()` prepares the value by calling `connection.ops.prep_for_like_query()` to escape special characters, then applies `param_pattern` (which for IContains inherits from Contains, so it's `"%%%s%%"` for wrapping with wildcards)
- **django/db/models/lookups.py:588-601** — `PatternLookup.get_rhs_op()` returns either pattern_ops or operators from connection

**8. PostgreSQL operator lookup:**
- **django/db/backends/postgresql/base.py:144-159** — Database backend's `operators` dict defines:
  - `"icontains": "LIKE UPPER(%s)"`
- **django/db/backends/postgresql/base.py:172-179** — `pattern_ops` dict for expressions:
  - `"icontains": "LIKE '%%' || UPPER({}) || '%%'"`
- **django/db/backends/postgresql/base.py:169-171** — `pattern_esc` for escaping in pattern expressions

**9. Final SQL generation:**
- **django/db/models/sql/where.py:116-160** — `WhereNode.as_sql()` compiles each child condition
- **django/db/models/sql/compiler.py:593-599** — When each Lookup child is compiled, `as_sql()` produces the final clause

**Result for PostgreSQL:** 
```sql
WHERE UPPER(name) LIKE UPPER('%x%')
```