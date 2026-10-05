Now I can trace the complete flow from `Model.objects.filter(name__icontains="x")` to the PostgreSQL SQL. Here's the execution path:

## **1. QuerySet.filter() Entry Point**
**django/db/models/query.py:1724**
```
def filter(self, *args, **kwargs):
    return self._filter_or_exclude(False, args, kwargs)
```
Initiates filtering by calling `_filter_or_exclude`, which eventually calls `Query.add_q()`.

## **2. Query.add_q() calls Query.build_filter()**
**django/db/models/sql/query.py:1499-1569**
`build_filter()` receives the filter tuple `("name__icontains", "x")` and:
- Line 1562: Calls `solve_lookup_type("name__icontains")` to parse the field and lookup parts

## **3. Query.solve_lookup_type() - Split the Field and Lookup**
**django/db/models/sql/query.py:1344-1365**
```python
def solve_lookup_type(self, lookup, summarize=False):
    lookup_splitted = lookup.split(LOOKUP_SEP)  # ["name", "icontains"]
    # ... resolves field via names_to_path ...
    return lookup_parts, field_parts, False  # Returns (["icontains"], ["name"], False)
```

## **4. Query.build_filter() continues - Create Column Reference**
**django/db/models/sql/query.py:1570-1624**
- Lines 1588-1594: `setup_joins()` resolves the field to a table alias
- Line 1618 or 1622: Creates a `Col` object representing the column reference
- Line 1624: **Calls `build_lookup(["icontains"], col, "x")`**

## **5. Query.build_lookup() - Instantiate the Lookup Class**
**django/db/models/sql/query.py:1415-1459**
```python
def build_lookup(self, lookups, lhs, rhs):
    *transforms, lookup_name = lookups or ["exact"]  # lookup_name = "icontains"
    lookup_class = lhs.get_lookup(lookup_name)        # Gets IContains class
    lookup = lookup_class(lhs, rhs)                   # Instantiates IContains("x")
    return lookup
```

## **6. Lookup Hierarchy Resolution**
**django/db/models/lookups.py:631-632**
```python
@Field.register_lookup
class IContains(Contains):
    lookup_name = "icontains"
```

Extends:
- `Contains` (line 626) → `PatternLookup` (line 584) → `BuiltinLookup` (line 234) → `Lookup` (line 29)

## **7. SQL Compilation - Compiler.compile()**
**django/db/models/sql/compiler.py:593-599**
When the WHERE clause is compiled:
```python
def compile(self, node):
    vendor_impl = getattr(node, "as_" + self.connection.vendor, None)  # Looks for "as_postgresql"
    if vendor_impl:
        sql, params = vendor_impl(self, self.connection)
    else:
        sql, params = node.as_sql(self, self.connection)
    return sql, params
```

## **8. BuiltinLookup.as_sql() - Generate SQL**
**django/db/models/lookups.py:243-248**
```python
def as_sql(self, compiler, connection):
    lhs_sql, params = self.process_lhs(compiler, connection)  # e.g., "table.name"
    rhs_sql, rhs_params = self.process_rhs(compiler, connection)  # e.g., "%x%"
    params = (*params, *rhs_params)
    rhs_sql = self.get_rhs_op(connection, rhs_sql)  # e.g., "ILIKE %s"
    return "%s %s" % (lhs_sql, rhs_sql), params    # "table.name ILIKE %s"
```

## **9. PatternLookup.process_rhs() - Prepare Value with Wildcards**
**django/db/models/lookups.py:603-616**
```python
def process_rhs(self, qn, connection):
    rhs, params = super().process_rhs(qn, connection)
    if self.is_simple_lookup:
        param = connection.ops.prep_for_like_query(params[0])  # Escape % and _
        if connection.features.pattern_lookup_needs_param_pattern:
            param = self.param_pattern % param  # Contains uses "%%%s%%"
        params = (param, *params[1:])
    return rhs, params
```
For `IContains`, inherits `param_pattern = "%%%s%%"` from `Contains`.

## **10. BuiltinLookup.get_rhs_op() - Get the Operator**
**django/db/models/lookups.py:250-251**
```python
def get_rhs_op(self, connection, rhs):
    return connection.operators[self.lookup_name] % rhs  # Gets "ILIKE %s" for PostgreSQL
```

## **11. PostgreSQL Operators**
**django/db/backends/postgresql/base.py** (via `connection.operators`)
The PostgreSQL backend registers:
- `"icontains": "ILIKE %s"` (case-insensitive LIKE)

## **Final SQL for PostgreSQL:**

```sql
SELECT * FROM app_model WHERE "app_model"."name" ILIKE %s
```

With parameter: `['%x%']` (the literal value with wildcards prepended/appended)

---

### Key Reference Points:

| Component | File:Line |
|-----------|-----------|
| QuerySet.filter() | django/db/models/query.py:1724 |
| build_filter() | django/db/models/sql/query.py:1499 |
| solve_lookup_type() | django/db/models/sql/query.py:1344 |
| build_lookup() | django/db/models/sql/query.py:1415 |
| IContains lookup class | django/db/models/lookups.py:631 |
| BuiltinLookup.as_sql() | django/db/models/lookups.py:243 |
| PatternLookup.process_rhs() | django/db/models/lookups.py:603 |
| SQLCompiler.compile() | django/db/models/sql/compiler.py:593 |
| prep_for_like_query() | django/db/backends/base/operations.py:537 |