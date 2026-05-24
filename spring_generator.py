"""Spring Boot 3 generator — Entity, Repository, Service, Controller, DTOs, Exception, Config."""

from .utils import to_pascal, to_camel, to_kebab


class SpringGenerator:

    def __init__(self, schema: dict, pkg: str, api_prefix: str):
        self.schema     = schema
        self.pkg        = pkg
        self.api_prefix = api_prefix.rstrip("/")

    # ── Public entry point ──────────────────────────────────────────────────
    def generate(self, table: str) -> dict:
        tbl   = self.schema[table]
        cls   = to_pascal(table)
        files = {}
        base  = f"spring/src/main/java/{self.pkg.replace('.','/')}"

        files[f"{base}/entity/{cls}.java"]                  = self._entity(table, tbl)
        files[f"{base}/dto/{cls}Dto.java"]                  = self._dto(table, tbl)
        files[f"{base}/dto/{cls}CreateRequest.java"]        = self._create_request(table, tbl)
        files[f"{base}/repository/{cls}Repository.java"]    = self._repository(table, tbl)
        files[f"{base}/service/{cls}Service.java"]          = self._service_interface(table, tbl)
        files[f"{base}/service/impl/{cls}ServiceImpl.java"] = self._service_impl(table, tbl)
        files[f"{base}/controller/{cls}Controller.java"]    = self._controller(table, tbl)
        files[f"{base}/exception/ResourceNotFoundException.java"] = self._not_found_ex()
        files[f"{base}/exception/GlobalExceptionHandler.java"]    = self._global_handler()
        files[f"{base}/config/AppConfig.java"]              = self._app_config()
        files[f"spring/src/main/resources/application.properties"] = self._app_props()
        return files

    # ── Entity ────────────────────────────────────────────────────────────────
    def _entity(self, table: str, tbl: dict) -> str:
        cls    = to_pascal(table)
        pk     = next((f for f in tbl["fields"] if f["is_pk"]), None)
        fk_map = {fk["column"]: fk for fk in tbl["foreign_keys"]}

        imports = {
            "jakarta.persistence.*",
            "lombok.Data",
            "lombok.NoArgsConstructor",
            "lombok.AllArgsConstructor",
        }
        extra_imports = set()
        fk_fields_code = []
        regular_fields = []

        for f in tbl["fields"]:
            java_type = f["java_type"]
            if java_type == "BigDecimal":
                extra_imports.add("java.math.BigDecimal")
            elif java_type in ("LocalDate","LocalDateTime"):
                extra_imports.add(f"java.time.{java_type}")

            if f["is_pk"]:
                regular_fields.append(f"    @Id\n    @GeneratedValue(strategy = GenerationType.IDENTITY)\n    private {java_type} {f['name']};")
            elif f["name"] in fk_map:
                fk      = fk_map[f["name"]]
                ref_cls = to_pascal(fk["ref_table"])
                fk_fields_code.append(
                    f"    @ManyToOne(fetch = FetchType.LAZY)\n"
                    f"    @JoinColumn(name = \"{f['name']}\", nullable = {str(f['required']).lower()})\n"
                    f"    private {ref_cls} {to_camel(fk['ref_table'])};"
                )
                imports.add(f"{self.pkg}.entity.{ref_cls}")
            else:
                col_ann = f'    @Column(name = "{f["name"]}"'
                if f["required"]:
                    col_ann += ", nullable = false"
                if f["max_len"]:
                    col_ann += f", length = {f['max_len']}"
                col_ann += ")"
                val_str = "null"
                regular_fields.append(f"{col_ann}\n    private {java_type} {f['name']};")

        all_imports  = "\n".join(f"import {i};" for i in sorted(imports | extra_imports))
        fields_code  = "\n\n".join(regular_fields + fk_fields_code)

        return f"""package {self.pkg}.entity;

{all_imports}

@Data
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "{table}")
public class {cls} {{

{fields_code}
}}
"""

    # ── DTO ───────────────────────────────────────────────────────────────────
    def _dto(self, table: str, tbl: dict) -> str:
        cls = to_pascal(table)
        extra = set()
        fields_code = []
        for f in tbl["fields"]:
            jt = f["java_type"]
            if jt == "BigDecimal": extra.add("java.math.BigDecimal")
            elif jt in ("LocalDate","LocalDateTime"): extra.add(f"java.time.{jt}")
            fields_code.append(f"    private {jt} {f['name']};")

        imports = "\n".join(f"import {i};" for i in sorted(extra))
        return f"""package {self.pkg}.dto;

import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
{imports}

@Data
@NoArgsConstructor
@AllArgsConstructor
public class {cls}Dto {{

{"".join(f for f in [f + chr(10) for f in fields_code])}
}}
"""

    # ── Create Request (validation annotations) ────────────────────────────
    def _create_request(self, table: str, tbl: dict) -> str:
        cls     = to_pascal(table)
        extra   = set()
        val_imp = set()
        fields  = []

        for f in tbl["fields"]:
            if f["is_identity"]:
                continue
            jt = f["java_type"]
            if jt == "BigDecimal": extra.add("java.math.BigDecimal")
            elif jt in ("LocalDate","LocalDateTime"): extra.add(f"java.time.{jt}")

            annotations = []
            if f["required"]:
                annotations.append("    @NotNull(message = \"" + f["name"] + " is required\")")
                val_imp.add("jakarta.validation.constraints.NotNull")
            if jt == "String":
                if f["required"]:
                    annotations.append("    @NotBlank(message = \"" + f["name"] + " cannot be blank\")")
                    val_imp.add("jakarta.validation.constraints.NotBlank")
                if f["max_len"]:
                    annotations.append(f'    @Size(max = {f["max_len"]}, message = "{f["name"]} max {f["max_len"]} chars")')
                    val_imp.add("jakarta.validation.constraints.Size")
            if jt in ("Integer","Long","Short","BigDecimal","Double","Float"):
                annotations.append(f'    @NotNull(message = "{f["name"]} is required")')
                val_imp.add("jakarta.validation.constraints.NotNull")

            ann_str = "\n".join(annotations)
            if ann_str:
                fields.append(f"{ann_str}\n    private {jt} {f['name']};")
            else:
                fields.append(f"    private {jt} {f['name']};")

        all_imp = "\n".join(f"import {i};" for i in sorted(extra | val_imp))
        return f"""package {self.pkg}.dto;

import lombok.Data;
{all_imp}

@Data
public class {cls}CreateRequest {{

{"".join(f + chr(10) for f in fields)}
}}
"""

    # ── Repository ─────────────────────────────────────────────────────────
    def _repository(self, table: str, tbl: dict) -> str:
        cls = to_pascal(table)
        pk  = next((f for f in tbl["fields"] if f["is_pk"]), tbl["fields"][0])
        # extra query methods for indexed fields
        extra = []
        for f in tbl["fields"]:
            if f.get("indexed") and not f["is_pk"]:
                jt = f["java_type"]
                mn = to_camel(f["name"])
                extra.append(
                    f'    java.util.List<{cls}> findBy{to_pascal(f["name"])}({jt} {mn});'
                )
        extra_code = "\n".join(extra)

        return f"""package {self.pkg}.repository;

import {self.pkg}.entity.{cls};
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

@Repository
public interface {cls}Repository extends JpaRepository<{cls}, {pk['java_type']}> {{

{extra_code}
}}
"""

    # ── Service Interface ──────────────────────────────────────────────────
    def _service_interface(self, table: str, tbl: dict) -> str:
        cls = to_pascal(table)
        pk  = next((f for f in tbl["fields"] if f["is_pk"]), tbl["fields"][0])
        return f"""package {self.pkg}.service;

import {self.pkg}.dto.{cls}Dto;
import {self.pkg}.dto.{cls}CreateRequest;
import java.util.List;

public interface {cls}Service {{
    List<{cls}Dto> findAll();
    {cls}Dto findById({pk['java_type']} id);
    {cls}Dto create({cls}CreateRequest request);
    {cls}Dto update({pk['java_type']} id, {cls}CreateRequest request);
    void delete({pk['java_type']} id);
}}
"""

    # ── Service Impl ──────────────────────────────────────────────────────
    def _service_impl(self, table: str, tbl: dict) -> str:
        cls    = to_pascal(table)
        camel  = to_camel(table)
        pk     = next((f for f in tbl["fields"] if f["is_pk"]), tbl["fields"][0])
        fk_map = {fk["column"]: fk for fk in tbl["foreign_keys"]}

        # FK repo injections
        fk_repo_fields = []
        fk_repo_imports = []
        for fk in tbl["foreign_keys"]:
            ref_cls  = to_pascal(fk["ref_table"])
            ref_caml = to_camel(fk["ref_table"])
            fk_repo_fields.append(f"    private final {ref_cls}Repository {ref_caml}Repository;")
            fk_repo_imports.append(f"import {self.pkg}.repository.{ref_cls}Repository;")
            fk_repo_imports.append(f"import {self.pkg}.entity.{ref_cls};")

        # Mapping: entity -> dto
        to_dto_lines = []
        to_entity_lines = []
        for f in tbl["fields"]:
            if f["name"] in fk_map:
                fk      = fk_map[f["name"]]
                ref_cls = to_pascal(fk["ref_table"])
                ref_caml = to_camel(fk["ref_table"])
                to_dto_lines.append(
                    f"        dto.set{to_pascal(f['name'])}(entity.get{to_pascal(ref_caml)}() != null ? "
                    f"entity.get{to_pascal(ref_caml)}().get{to_pascal(fk['ref_column'])}() : null);"
                )
                to_entity_lines.append(
                    f"        if (request.get{to_pascal(f['name'])}() != null) {{\n"
                    f"            {ref_cls} {ref_caml} = {ref_caml}Repository.findById(request.get{to_pascal(f['name'])}())\n"
                    f"                .orElseThrow(() -> new ResourceNotFoundException(\"{ref_cls} not found with id: \" + request.get{to_pascal(f['name'])}()));\n"
                    f"            entity.set{to_pascal(ref_caml)}({ref_caml});\n        }}"
                )
            else:
                if not f["is_pk"]:
                    to_dto_lines.append(f"        dto.set{to_pascal(f['name'])}(entity.get{to_pascal(f['name'])}());")
                    to_entity_lines.append(f"        entity.set{to_pascal(f['name'])}(request.get{to_pascal(f['name'])}());")
                else:
                    to_dto_lines.append(f"        dto.set{to_pascal(f['name'])}(entity.get{to_pascal(f['name'])}());")

        return f"""package {self.pkg}.service.impl;

import {self.pkg}.dto.{cls}Dto;
import {self.pkg}.dto.{cls}CreateRequest;
import {self.pkg}.entity.{cls};
import {self.pkg}.exception.ResourceNotFoundException;
import {self.pkg}.repository.{cls}Repository;
import {self.pkg}.service.{cls}Service;
{"".join(i + chr(10) for i in sorted(set(fk_repo_imports)))}
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.List;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class {cls}ServiceImpl implements {cls}Service {{

    private final {cls}Repository {camel}Repository;
{"".join(f + chr(10) for f in fk_repo_fields)}

    // ── Read ─────────────────────────────────────────────────────────────
    @Override
    @Transactional(readOnly = true)
    public List<{cls}Dto> findAll() {{
        log.debug("Fetching all {table} records");
        return {camel}Repository.findAll()
                .stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }}

    @Override
    @Transactional(readOnly = true)
    public {cls}Dto findById({pk['java_type']} id) {{
        log.debug("Fetching {table} with id: {{}}", id);
        {cls} entity = {camel}Repository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("{cls} not found with id: " + id));
        return toDto(entity);
    }}

    // ── Create ────────────────────────────────────────────────────────────
    @Override
    @Transactional
    public {cls}Dto create({cls}CreateRequest request) {{
        log.info("Creating {table} record");
        try {{
            {cls} entity = new {cls}();
            mapRequestToEntity(request, entity);
            {cls} saved = {camel}Repository.save(entity);
            log.info("{cls} created with id: {{}}", saved.get{to_pascal(pk['name'])}());
            return toDto(saved);
        }} catch (ResourceNotFoundException e) {{
            throw e;
        }} catch (Exception e) {{
            log.error("Error creating {cls}: {{}}", e.getMessage(), e);
            throw new RuntimeException("Failed to create {cls}: " + e.getMessage(), e);
        }}
    }}

    // ── Update ────────────────────────────────────────────────────────────
    @Override
    @Transactional
    public {cls}Dto update({pk['java_type']} id, {cls}CreateRequest request) {{
        log.info("Updating {table} with id: {{}}", id);
        try {{
            {cls} entity = {camel}Repository.findById(id)
                    .orElseThrow(() -> new ResourceNotFoundException("{cls} not found with id: " + id));
            mapRequestToEntity(request, entity);
            {cls} saved = {camel}Repository.save(entity);
            log.info("{cls} updated: {{}}", id);
            return toDto(saved);
        }} catch (ResourceNotFoundException e) {{
            throw e;
        }} catch (Exception e) {{
            log.error("Error updating {cls} id={{}}: {{}}", id, e.getMessage(), e);
            throw new RuntimeException("Failed to update {cls}: " + e.getMessage(), e);
        }}
    }}

    // ── Delete ────────────────────────────────────────────────────────────
    @Override
    @Transactional
    public void delete({pk['java_type']} id) {{
        log.info("Deleting {table} with id: {{}}", id);
        try {{
            if (!{camel}Repository.existsById(id)) {{
                throw new ResourceNotFoundException("{cls} not found with id: " + id);
            }}
            {camel}Repository.deleteById(id);
            log.info("{cls} deleted: {{}}", id);
        }} catch (ResourceNotFoundException e) {{
            throw e;
        }} catch (Exception e) {{
            log.error("Error deleting {cls} id={{}}: {{}}", id, e.getMessage(), e);
            throw new RuntimeException("Failed to delete {cls}: " + e.getMessage(), e);
        }}
    }}

    // ── Mappers ───────────────────────────────────────────────────────────
    private {cls}Dto toDto({cls} entity) {{
        {cls}Dto dto = new {cls}Dto();
{"".join(line + chr(10) for line in to_dto_lines)}        return dto;
    }}

    private void mapRequestToEntity({cls}CreateRequest request, {cls} entity) {{
{"".join(line + chr(10) for line in to_entity_lines)}    }}
}}
"""

    # ── Controller ────────────────────────────────────────────────────────
    def _controller(self, table: str, tbl: dict) -> str:
        cls   = to_pascal(table)
        camel = to_camel(table)
        kebab = to_kebab(table)
        pk    = next((f for f in tbl["fields"] if f["is_pk"]), tbl["fields"][0])
        url   = f"{self.api_prefix}/{kebab.replace('-','/')}"

        return f"""package {self.pkg}.controller;

import {self.pkg}.dto.{cls}Dto;
import {self.pkg}.dto.{cls}CreateRequest;
import {self.pkg}.service.{cls}Service;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@Slf4j
@RestController
@RequestMapping("{url}")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class {cls}Controller {{

    private final {cls}Service {camel}Service;

    // GET /all
    @GetMapping
    public ResponseEntity<List<{cls}Dto>> getAll() {{
        log.debug("GET {url}");
        return ResponseEntity.ok({camel}Service.findAll());
    }}

    // GET /:id
    @GetMapping("/{{{camel}Id}}")
    public ResponseEntity<{cls}Dto> getById(@PathVariable {pk['java_type']} {camel}Id) {{
        log.debug("GET {url}/{{}}", {camel}Id);
        return ResponseEntity.ok({camel}Service.findById({camel}Id));
    }}

    // POST /
    @PostMapping
    public ResponseEntity<{cls}Dto> create(@Valid @RequestBody {cls}CreateRequest request) {{
        log.debug("POST {url}");
        {cls}Dto created = {camel}Service.create(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }}

    // PUT /:id
    @PutMapping("/{{{camel}Id}}")
    public ResponseEntity<{cls}Dto> update(
            @PathVariable {pk['java_type']} {camel}Id,
            @Valid @RequestBody {cls}CreateRequest request) {{
        log.debug("PUT {url}/{{}}", {camel}Id);
        return ResponseEntity.ok({camel}Service.update({camel}Id, request));
    }}

    // DELETE /:id
    @DeleteMapping("/{{{camel}Id}}")
    public ResponseEntity<Void> delete(@PathVariable {pk['java_type']} {camel}Id) {{
        log.debug("DELETE {url}/{{}}", {camel}Id);
        {camel}Service.delete({camel}Id);
        return ResponseEntity.noContent().build();
    }}
}}
"""

    # ── Exception classes ─────────────────────────────────────────────────
    def _not_found_ex(self) -> str:
        return f"""package {self.pkg}.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.NOT_FOUND)
public class ResourceNotFoundException extends RuntimeException {{
    public ResourceNotFoundException(String message) {{
        super(message);
    }}
}}
"""

    def _global_handler(self) -> str:
        return f"""package {self.pkg}.exception;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {{

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(ResourceNotFoundException ex) {{
        log.warn("Not found: {{}}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(new ErrorResponse(HttpStatus.NOT_FOUND.value(), ex.getMessage()));
    }}

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException ex) {{
        Map<String, String> errors = new HashMap<>();
        ex.getBindingResult().getAllErrors().forEach(err -> {{
            String field = ((FieldError) err).getField();
            errors.put(field, err.getDefaultMessage());
        }});
        ErrorResponse resp = new ErrorResponse(HttpStatus.BAD_REQUEST.value(), "Validation failed");
        resp.setDetails(errors);
        return ResponseEntity.badRequest().body(resp);
    }}

    @ExceptionHandler(RuntimeException.class)
    public ResponseEntity<ErrorResponse> handleRuntime(RuntimeException ex) {{
        log.error("Runtime error: {{}}", ex.getMessage(), ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new ErrorResponse(500, ex.getMessage()));
    }}

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleAll(Exception ex) {{
        log.error("Unexpected error: {{}}", ex.getMessage(), ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new ErrorResponse(500, "An unexpected error occurred"));
    }}

    // ── Inner error response ──────────────────────────────────────────────
    public static class ErrorResponse {{
        public int status;
        public String message;
        public LocalDateTime timestamp = LocalDateTime.now();
        public Map<String, String> details;

        public ErrorResponse(int status, String message) {{
            this.status  = status;
            this.message = message;
        }}
        public void setDetails(Map<String, String> details) {{ this.details = details; }}
    }}
}}
"""

    # ── Config ────────────────────────────────────────────────────────────
    def _app_config(self) -> str:
        return f"""package {self.pkg}.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class AppConfig {{

    @Bean
    public WebMvcConfigurer corsConfigurer() {{
        return new WebMvcConfigurer() {{
            @Override
            public void addCorsMappings(CorsRegistry registry) {{
                registry.addMapping("/**")
                        .allowedOrigins("*")
                        .allowedMethods("GET","POST","PUT","DELETE","OPTIONS")
                        .allowedHeaders("*");
            }}
        }};
    }}
}}
"""

    def _app_props(self) -> str:
        return """# Spring Boot Application Properties
spring.application.name=fintech-app
server.port=8080

# DataSource — update credentials
spring.datasource.url=jdbc:sqlserver://localhost:1433;databaseName=fintech;encrypt=false
spring.datasource.username=sa
spring.datasource.password=YourPassword!
spring.datasource.driver-class-name=com.microsoft.sqlserver.jdbc.SQLServerDriver

# JPA / Hibernate
spring.jpa.database-platform=org.hibernate.dialect.SQLServerDialect
spring.jpa.hibernate.ddl-auto=validate
spring.jpa.show-sql=false
spring.jpa.properties.hibernate.format_sql=true

# Transaction management
spring.transaction.default-timeout=30

# Logging
logging.level.root=WARN
logging.level.com.fintech=DEBUG
logging.level.org.springframework.transaction=DEBUG
"""
