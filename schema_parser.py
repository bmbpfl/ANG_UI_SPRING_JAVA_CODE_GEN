import re

class SchemaParser:
    """Parse the CSV schema into a structured dict."""

    JAVA_TYPE_MAP = {
        "int": "Integer", "bigint": "Long", "smallint": "Short",
        "tinyint": "Byte", "decimal": "BigDecimal", "numeric": "BigDecimal",
        "float": "Double", "real": "Float", "double": "Double",
        "varchar": "String", "nvarchar": "String", "char": "String",
        "text": "String", "ntext": "String", "char(1)": "String",
        "date": "LocalDate", "datetime": "LocalDateTime",
        "smalldatetime": "LocalDateTime", "timestamp": "LocalDateTime",
        "boolean": "Boolean", "bit": "Boolean",
    }

    TS_TYPE_MAP = {
        "int": "number", "bigint": "number", "smallint": "number",
        "tinyint": "number", "decimal": "number", "numeric": "number",
        "float": "number", "real": "number", "double": "number",
        "varchar": "string", "nvarchar": "string", "char": "string",
        "text": "string", "ntext": "string", "char(1)": "string",
        "date": "string", "datetime": "string",
        "smalldatetime": "string", "timestamp": "string",
        "boolean": "boolean", "bit": "boolean",
    }

    HTML_INPUT_MAP = {
        "int": "number", "bigint": "number", "smallint": "number",
        "tinyint": "number", "decimal": "number", "numeric": "number",
        "float": "number", "real": "number", "double": "number",
        "varchar": "text", "nvarchar": "text", "char": "text",
        "text": "textarea", "char(1)": "text",
        "date": "date", "datetime": "datetime-local",
        "smalldatetime": "datetime-local", "timestamp": "datetime-local",
        "boolean": "checkbox", "bit": "checkbox",
    }

    def parse(self):
        schema = {}
        for _, row in self.df.iterrows():
            tbl = str(row["table_name"]).strip()
            if tbl not in schema:
                schema[tbl] = {"fields": [], "foreign_keys": []}

            field_name  = str(row["field_name"]).strip()
            raw_type    = str(row["data_type"]).strip().lower()
            is_identity = str(row.get("identity","")).strip().lower() == "yes"
            max_len     = str(row.get("len","")).strip()
            decimals    = str(row.get("dec","")).strip()
            indexed     = str(row.get("index","")).strip().lower() == "yes"
            constraint  = str(row.get("constraint","")).strip()

            is_pk = is_identity  # identity columns are PKs
            required = not is_pk  # non-PK fields required by default

            java_type = self.JAVA_TYPE_MAP.get(raw_type, "String")
            ts_type   = self.TS_TYPE_MAP.get(raw_type, "string")
            html_input = self.HTML_INPUT_MAP.get(raw_type, "text")

            field = {
                "name":       field_name,
                "db_type":    raw_type,
                "java_type":  java_type,
                "ts_type":    ts_type,
                "html_input": html_input,
                "is_pk":      is_pk,
                "is_identity": is_identity,
                "required":   required and not is_pk,
                "max_len":    max_len if max_len else None,
                "decimals":   decimals if decimals else None,
                "indexed":    indexed,
            }
            schema[tbl]["fields"].append(field)

            # Parse FK constraint
            if constraint:
                fk_match = re.search(
                    r'FOREIGN KEY\s*\((\w+)\)\s*REFERENCES\s+(\w+)\((\w+)\)',
                    constraint, re.IGNORECASE
                )
                if fk_match:
                    schema[tbl]["foreign_keys"].append({
                        "column":     fk_match.group(1),
                        "ref_table":  fk_match.group(2),
                        "ref_column": fk_match.group(3),
                    })

        return schema

    def __init__(self, df):
        self.df = df
