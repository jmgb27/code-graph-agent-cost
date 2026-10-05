Now I'll compile the complete trace for you.

## Trace: `Model.objects.filter(name__icontains="x")` → PostgreSQL SQL

### 1. QuerySet Call Flow

**django/db/models/query.py:1724** — `QuerySet.filter()`
```python
def filter(self, *args, **kwargs):
    self._not_support_combined_queries("filter")
    return self._filter_or_exclude(False, args, kwargs)
```

**django/db/models/query.py:1740** — `QuerySet._filter_or_exclude()`
```python
def _filter_or_exclude(self, negate, args, kwargs):
    clone = self._chain()
    if self._defer_next_filter:
        self._defer_next_filter = False
        clone._deferred_filter = negate, args, kwargs
    else:
        clone._filter_or_exclude_inplace(negate, args, kwargs)
    return clone
```

**django/db/models/query.py:1751** — `QuerySet._filter_or_exclude_inplace()`
```python
def _filter_or_exclude_inplace(self, negate, args, kwargs):
    if negate:
        self._query.add_q(~Q(*args, **kwargs))
    else:
        self._query.add_q(Q(*args, **kwargs))  # calls Query.add_q()
```

### 2. Query Object Processing

**django/db/models/sql/query.py:1674** — `Query.add_q()`
```python
def add_q(self, q_object, reuse_all=False):
    existing_inner = {a for a in self.alias_map if self.alias_map[a].join_type == INNER}
    clause, _ = self._add_q(q_object, can_reuse)  # calls _add_q()
    if clause:
        self.where.add(clause, AND)
```

**django/db/models/sql/query.py:1703** — `Query._add_q()`
```python
def _add_q(self, q_object, used_aliases, ...):
    for child in q_object.children:
        child_clause, needed_inner = self.build_filter(  # calls build_filter()
            child,
            can_reuse=used_aliases,
            ...
        )
```

### 3. Filter Building & Lookup Resolution

**django/db/models/sql/query.py:1499** — `Query.build_filter()`
```python
def build_filter(self, filter_expr, ...):
    # filter_expr is ('name__icontains', 'x')
    arg, value = filter_expr
    lookups, parts, reffed_expression = self.solve_lookup_type(arg, summarize)  # line 1562
    # ... setup joins and column reference ...
    condition = self.build_lookup(lookups, col, value)  # line 1624
    return WhereNode([condition], connector=AND), []
```

**django/db/models/sql/query.py:1344** — `Query.solve_lookup_type()`
```python
def solve_lookup_type(self, lookup, summarize=False):
    lookup_splitted = lookup.split(LOOKUP_SEP)  # "name__icontains" → ["name", "icontains"]
    _, field, _, lookup_parts = self.names_to_path(lookup_splitted, self.get_meta())
    # Returns: (["icontains"], ["name"], False)
    return lookup_parts, field_parts, False
```

**django/db/models/sql/query.py:1415** — `Query.build_lookup()`
```python
def build_lookup(self, lookups, lhs, rhs):
    *transforms, lookup_name = lookups or ["exact"]  # lookup_name = "icontains"
    for name in transforms:
        lhs = self.try_transform(lhs, name, lookups)
    
    lookup_class = lhs.get_lookup(lookup_name)  # line 1430 - resolves to IContains class
    if not lookup_class:
        lhs = self.try_transform(lhs, lookup_name)
        lookup_name = "exact"
        lookup_class = lhs.get_lookup(lookup_name)
    
    lookup = lookup_class(lhs, rhs)  # line 1440 - instantiates IContains(col, "x")
    return lookup
```

### 4. Lookup Class Hierarchy & Registration

**django/db/models/query_utils.py:347** — `RegisterLookupMixin.get_lookup()`
```python
def get_lookup(self, lookup_name):
    found = self._get_lookup(lookup_name)  # searches registered lookups
    if found is None and hasattr(self, "output_field"):
        return self.output_field.get_lookup(lookup_name)
    if found is not None and not issubclass(found, Lookup):
        return None
    return found  # returns IContains class
```

**Lookup Class Hierarchy:**
- **django/db/models/lookups.py:631** — `IContains` (registered with `@Field.register_lookup`)
- **django/db/models/lookups.py:626** — `Contains` (parent)
- **django/db/models/lookups.py:584** — `PatternLookup` (parent)
- **django/db/models/lookups.py:234** — `BuiltinLookup` (parent)
- **django/db/models/lookups.py:29** — `Lookup` base class

### 5. SQL Compilation

**django/db/models/sql/compiler.py:776** — `SQLCompiler.as_sql()`
```python
def as_sql(self, with_limits=True, with_col_aliases=False):
    where, w_params = (
        self.compile(self.where) if self.where is not None else ("", [])
    )  # line 814-815
```

**django/db/models/sql/compiler.py:593** — `SQLCompiler.compile()`
```python
def compile(self, node):
    vendor_impl = getattr(node, "as_" + self.connection.vendor, None)
    if vendor_impl:
        sql, params = vendor_impl(self, self.connection)
    else:
        sql, params = node.as_sql(self, self.connection)
    return sql, params
```

**django/db/models/sql/where.py:116** — `WhereNode.as_sql()`
```python
def as_sql(self, compiler, connection):
    result = []
    result_params = []
    for child in self.children:  # child is the IContains lookup
        try:
            sql, params = compiler.compile(child)  # line 151
        except EmptyResultSet:
            empty_needed -= 1
        else:
            if sql:
                result.append(sql)
                result_params.extend(params)
    conn = " %s " % self.connector
    sql_string = conn.join(result)
    return sql_string, result_params
```

**django/db/models/lookups.py:243** — `BuiltinLookup.as_sql()`
```python
def as_sql(self, compiler, connection):
    lhs_sql, params = self.process_lhs(compiler, connection)  # line 244
    rhs_sql, rhs_params = self.process_rhs(compiler, connection)  # line 245
    params = (*params, *rhs_params)
    rhs_sql = self.get_rhs_op(connection, rhs_sql)  # line 247
    return "%s %s" % (lhs_sql, rhs_sql), params
```

**django/db/models/lookups.py:235** — `BuiltinLookup.process_lhs()`
```python
def process_lhs(self, compiler, connection, lhs=None):
    lhs_sql, params = super().process_lhs(compiler, connection, lhs)
    field_internal_type = self.lhs.output_field.get_internal_type()
    lhs_sql = (
        connection.ops.lookup_cast(self.lookup_name, field_internal_type) % lhs_sql
    )  # line 239 - applies PostgreSQL lookup_cast
    return lhs_sql, tuple(params)
```

**django/db/models/lookups.py:588** — `PatternLookup.get_rhs_op()`
```python
def get_rhs_op(self, connection, rhs):
    if not self.is_simple_lookup:
        pattern = connection.pattern_ops[self.lookup_name].format(
            connection.pattern_esc
        )  # line 595 - uses PostgreSQL pattern_ops
        return pattern.format(rhs)
    else:
        return super().get_rhs_op(connection, rhs)  # line 601
```

**django/db/models/lookups.py:603** — `PatternLookup.process_rhs()`
```python
def process_rhs(self, qn, connection):
    rhs, params = super().process_rhs(qn, connection)
    if self.is_simple_lookup:
        param = connection.ops.prep_for_like_query(params[0])
        if connection.features.pattern_lookup_needs_param_pattern:
            param = self.param_pattern % param  # line 614 - applies param_pattern "%%%s%%"
        params = (param, *params[1:])
    return rhs, params
```

### 6. PostgreSQL Backend Specifics

**django/db/backends/postgresql/base.py:144-159** — PostgreSQL operators
```python
operators = {
    # ...
    "icontains": "LIKE UPPER(%s)",  # line 148
    # ...
}
```

**django/db/backends/postgresql/base.py:172-179** — PostgreSQL pattern_ops
```python
pattern_ops = {
    # ...
    "icontains": "LIKE '%%' || UPPER({}) || '%%'",  # line 174
    # ...
}
```

**django/db/backends/postgresql/operations.py:158** — `DatabaseOperations.lookup_cast()`
```python
def lookup_cast(self, lookup_type, internal_type=None):
    lookup = "%s"
    if lookup_type in ("icontains", ...):
        if internal_type not in ("IPAddressField", "GenericIPAddressField"):
            lookup = "%s::text"  # line 175 - cast to text
    
    if lookup_type in ("icontains", ...):
        lookup = "UPPER(%s)" % lookup  # line 179 - wrap with UPPER()
    
    return lookup
```

### Final SQL Generation Example

For `Model.objects.filter(name__icontains="x")`:

1. **LHS processing** → `UPPER("table"."name"::text)`
2. **RHS operator** → `LIKE UPPER(%s)` or `LIKE '%%' || UPPER({}) || '%%'`
3. **RHS value** → `%x%` (from param_pattern)
4. **Final SQL** → `UPPER("table"."name"::text) LIKE UPPER('%x%')`