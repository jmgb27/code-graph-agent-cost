Based on the CodeGraph analysis, here's the complete trace for `Model.objects.filter(name__icontains="x")` from QuerySet call to PostgreSQL SQL:

## Execution Flow

### 1. **QuerySet Entry Point**
- **django/db/models/query.py:1724** — `QuerySet.filter()` method
  - Calls `_filter_or_exclude(False, args, kwargs)`

### 2. **Query Building**
- **django/db/models/sql/query.py:1499** — `Query.build_filter()` method
  - Parses the filter expression `(arg, value)` pair
  - Calls `solve_lookup_type(arg)` to break apart the lookup string

### 3. **Lookup Type Resolution**
- **django/db/models/sql/query.py:1344** — `Query.solve_lookup_type()` method
  - Splits `"name__icontains"` via `LOOKUP_SEP` into:
    - Field parts: `["name"]`
    - Lookup parts: `["icontains"]`

### 4. **Lookup Instance Creation**
- **django/db/models/sql/query.py:1415** — `Query.build_lookup()` method
  - Gets the lookup class via `lhs.get_lookup("icontains")`
  - Instantiates the lookup: `IContains(lhs, rhs)`

### 5. **Lookup Class Hierarchy**
- **django/db/models/lookups.py:631** — `IContains` class
  - `lookup_name = "icontains"`
  - Extends `Contains` (inherits behavior from it)

- **django/db/models/lookups.py:626** — `Contains` class
  - `lookup_name = "contains"`
  - Extends `PatternLookup`

- **django/db/models/lookups.py:584** — `PatternLookup` class
  - `param_pattern = "%%%s%%"` (wraps values with wildcards)
  - Extends `BuiltinLookup`

- **django/db/models/lookups.py:234** — `BuiltinLookup` class
  - Base class for built-in lookups

### 6. **SQL Compilation Entry**
- **django/db/models/lookups.py:243** — `BuiltinLookup.as_sql()` method
  ```python
  def as_sql(self, compiler, connection):
      lhs_sql, params = self.process_lhs(compiler, connection)      # Line 244
      rhs_sql, rhs_params = self.process_rhs(compiler, connection)  # Line 245
      params = (*params, *rhs_params)                               # Line 246
      rhs_sql = self.get_rhs_op(connection, rhs_sql)               # Line 247
      return "%s %s" % (lhs_sql, rhs_sql), params                  # Line 248
  ```

### 7. **Left-Hand Side Compilation**
- **django/db/models/lookups.py:107** — `Lookup.process_lhs()` method
  - Resolves the left-hand side expression (the column reference)
  - **django/db/models/sql/compiler.py:593** — `SQLCompiler.compile()` method
    - Checks for vendor-specific implementations: `getattr(node, "as_" + self.connection.vendor, None)`
    - For PostgreSQL: checks for `as_postgresql()` method
    - Falls back to standard `as_sql()` method

### 8. **Right-Hand Side Compilation**
- **django/db/models/lookups.py:117** — `Lookup.process_rhs()` method (base implementation)
  - Handles value resolution and parameter preparation

- **django/db/models/lookups.py:603** — `PatternLookup.process_rhs()` method (overrides)
  - For simple lookups, applies pattern wrapping:
  - **django/db/models/lookups.py:614** — Wraps value with `param_pattern % param`
  - Calls `connection.ops.prep_for_like_query()` to prepare the value for LIKE/ILIKE

### 9. **Operator Resolution**
- **django/db/models/lookups.py:588** — `PatternLookup.get_rhs_op()` method
  - For PostgreSQL with `icontains`: gets operator from `connection.operators["icontains"]`
  - Result: `ILIKE` operator for PostgreSQL (case-insensitive LIKE)

### 10. **WHERE Clause Assembly**
- **django/db/models/sql/where.py:116** — `WhereNode.as_sql()` method
  - Compiles each child condition (the lookup)
  - **django/db/models/sql/compiler.py:593** — Calls `compiler.compile(child)` on the Lookup
  - Joins multiple conditions with `AND`/`OR` connectors

## Final PostgreSQL SQL Output

For `Model.objects.filter(name__icontains="x")`, the compiled SQL becomes:
```sql
WHERE "table_name"."name" ILIKE '%x%'
```

The trace path shows:
1. QuerySet → Query → build_filter → solve_lookup_type + build_lookup
2. Lookup instantiation (IContains → Contains → PatternLookup → BuiltinLookup)
3. as_sql() orchestrates: process_lhs + process_rhs + get_rhs_op
4. Compiler.compile() dispatches to vendor-specific or generic as_sql methods
5. Final SQL assembles: column ILIKE %x%