Based on my exploration of the Django codebase, here's the complete trace of `Model.objects.filter(name__icontains="x")` from the QuerySet call to PostgreSQL SQL:

## QuerySet.filter() Entry Point
**django/db/models/query.py:1724** — `QuerySet.filter()` calls `_filter_or_exclude(False, args, kwargs)`

## Filter Processing
**django/db/models/query.py:1740** — `_filter_or_exclude()` creates a new QuerySet clone and calls `_filter_or_exclude_inplace()`

This eventually calls `Query.add_q()`, which invokes:

## Lookup Type Resolution  
**django/db/models/sql/query.py:1344** — `Query.solve_lookup_type()`
- Splits `"name__icontains"` by `LOOKUP_SEP` (`"__"`) into parts: `["name", "icontains"]`
- Calls `names_to_path()` to resolve the field path
- Returns `lookup_parts = ["icontains"]`, `field_parts = ["name"]`, `field = CharField`

## Query Building
**django/db/models/sql/query.py:1499** — `Query.build_filter()`
- Calls `solve_lookup_type()` to get `["icontains"]` as the lookup list
- Calls `setup_joins()` to handle any field relationships
- Gets a `Col` object representing the `name` field
- **Calls `build_lookup(["icontains"], col, "x")`**

## Lookup Class Instantiation
**django/db/models/sql/query.py:1415** — `Query.build_lookup()`
- Extracts lookup name: `lookup_name = "icontains"`
- Calls `col.get_lookup("icontains")`
- This resolves to **IContains lookup class** at **django/db/models/lookups.py:631**:
  ```python
  class IContains(Contains):
      lookup_name = "icontains"
  ```
- IContains extends `Contains` which extends `PatternLookup` which extends `BuiltinLookup`
- Instantiates: `lookup = IContains(col, "x")`

## Lookup Processing
During `IContains.__init__()` (inherited from Lookup at **django/db/models/lookups.py:29**):
- Calls `get_prep_lookup()` to prepare the RHS value

## SQL Compilation
When the query executes, **django/db/models/sql/compiler.py:593** — `SQLCompiler.compile()` is called:

**For BuiltinLookup.as_sql()** at **django/db/models/lookups.py:243**:
1. Calls `process_lhs(compiler, connection)` 
   - For PostgreSQL at **django/db/backends/postgresql/operations.py:158**, `lookup_cast("icontains", "CharField")`:
     - Casts to text: `"%s::text"`
     - Applies UPPER for case-insensitive: `"UPPER(%s::text)"`
   
2. Calls `process_rhs(compiler, connection)`
   - Gets the parameterized value: `"%s"` with params `["x"]`

3. Calls `get_rhs_op(connection, rhs)` at **django/db/models/lookups.py:250**
   - Looks up in `connection.operators["icontains"]`
   - From **django/db/backends/postgresql/base.py:148**: `"LIKE UPPER(%s)"`
   - Formats as: `"LIKE UPPER(%s)"`

4. Combines: `"UPPER(name::text) LIKE UPPER(%s)"` with params `["x"]`

## Final SQL for PostgreSQL
The resulting SQL query:
```sql
SELECT ... WHERE UPPER("name"::text) LIKE UPPER(%s)
```

With parameter value: `"x"`

**Key files and line references:**
- QuerySet.filter: django/db/models/query.py:1724
- solve_lookup_type: django/db/models/sql/query.py:1344
- build_filter: django/db/models/sql/query.py:1499
- build_lookup: django/db/models/sql/query.py:1415
- IContains lookup: django/db/models/lookups.py:631
- PatternLookup: django/db/models/lookups.py:584
- BuiltinLookup.as_sql: django/db/models/lookups.py:243
- PostgreSQL lookup_cast: django/db/backends/postgresql/operations.py:158
- PostgreSQL operators: django/db/backends/postgresql/base.py:144-159
- SQLCompiler.compile: django/db/models/sql/compiler.py:593