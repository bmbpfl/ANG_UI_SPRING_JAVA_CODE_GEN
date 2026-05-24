"""Angular 16 code generator — model, service, component (TS + HTML + CSS)."""

from .utils import to_pascal, to_camel, to_kebab


class AngularGenerator:

    def __init__(self, schema: dict, pkg: str, api_prefix: str):
        self.schema     = schema
        self.pkg        = pkg
        self.api_prefix = api_prefix.rstrip("/")

    # ── Public entry point ──────────────────────────────────────────────────
    def generate(self, table: str) -> dict:
        tbl   = self.schema[table]
        files = {}
        base  = f"angular/src/app/{to_kebab(table)}"

        files[f"{base}/{to_kebab(table)}.model.ts"]        = self._model(table, tbl)
        files[f"{base}/{to_kebab(table)}.service.ts"]      = self._service(table, tbl)
        files[f"{base}/{to_kebab(table)}.component.ts"]    = self._component_ts(table, tbl)
        files[f"{base}/{to_kebab(table)}.component.html"]  = self._component_html(table, tbl)
        files[f"{base}/{to_kebab(table)}.component.css"]   = self._component_css()
        files[f"angular/src/app/app.module.ts"]             = self._app_module(table)
        files[f"angular/src/environments/environment.ts"]   = self._environment()
        return files

    # ── Model ────────────────────────────────────────────────────────────────
    def _model(self, table: str, tbl: dict) -> str:
        cls = to_pascal(table)
        fk_cols = {fk["column"] for fk in tbl["foreign_keys"]}
        fk_map  = {fk["column"]: fk for fk in tbl["foreign_keys"]}

        lines = [f"// Auto-generated model for {table}\n"]

        # FK reference models (inline)
        for fk in tbl["foreign_keys"]:
            ref = to_pascal(fk["ref_table"])
            lines.append(f"export interface {ref}Ref {{")
            ref_tbl = self.schema.get(fk["ref_table"])
            if ref_tbl:
                for f in ref_tbl["fields"]:
                    opt = "?" if not f["required"] else ""
                    lines.append(f"  {f['name']}{opt}: {f['ts_type']};")
            lines.append("}\n")

        lines.append(f"export interface {cls} {{")
        for f in tbl["fields"]:
            opt = "?" if not f["required"] or f["is_pk"] else ""
            lines.append(f"  {f['name']}{opt}: {f['ts_type']};")
        lines.append("}\n")

        # Create / Update DTOs (omit identity PK from create)
        non_pk = [f for f in tbl["fields"] if not f["is_identity"]]
        lines.append(f"export interface {cls}CreateDto {{")
        for f in non_pk:
            opt = "?" if not f["required"] else ""
            lines.append(f"  {f['name']}{opt}: {f['ts_type']};")
        lines.append("}\n")

        lines.append(f"export interface {cls}UpdateDto extends {cls}CreateDto {{")
        pk_fields = [f for f in tbl["fields"] if f["is_pk"]]
        for f in pk_fields:
            lines.append(f"  {f['name']}: {f['ts_type']};")
        lines.append("}\n")

        return "\n".join(lines)

    # ── Service ──────────────────────────────────────────────────────────────
    def _service(self, table: str, tbl: dict) -> str:
        cls    = to_pascal(table)
        kebab  = to_kebab(table)
        url    = f"{self.api_prefix}/{kebab.replace('-', '/')}"
        pk     = next((f for f in tbl["fields"] if f["is_pk"]), tbl["fields"][0])

        # FK services to import
        fk_imports = []
        fk_loaders = []
        for fk in tbl["foreign_keys"]:
            ref_cls  = to_pascal(fk["ref_table"])
            ref_keb  = to_kebab(fk["ref_table"])
            ref_url  = f"{self.api_prefix}/{ref_keb.replace('-', '/')}"
            fk_imports.append(f"import {{ {ref_cls} }} from '../{ref_keb}/{ref_keb}.model';")
            fk_loaders.append(f"""
  get{ref_cls}List(): Observable<{ref_cls}[]> {{
    return this.http.get<{ref_cls}[]>('{ref_url}').pipe(
      catchError(this.handleError<{ref_cls}[]>('get{ref_cls}List', []))
    );
  }}""")

        return f"""// Auto-generated service for {table}
import {{ Injectable }} from '@angular/core';
import {{ HttpClient, HttpHeaders, HttpErrorResponse }} from '@angular/common/http';
import {{ Observable, throwError, of }} from 'rxjs';
import {{ catchError, retry }} from 'rxjs/operators';
import {{ environment }} from '../../environments/environment';
import {{ {cls}, {cls}CreateDto, {cls}UpdateDto }} from './{kebab}.model';
{"".join(fk_imports)}

const HTTP_OPTIONS = {{
  headers: new HttpHeaders({{ 'Content-Type': 'application/json' }})
}};

@Injectable({{ providedIn: 'root' }})
export class {cls}Service {{

  private baseUrl = `${{environment.apiUrl}}{url}`;

  constructor(private http: HttpClient) {{}}

  // ── CRUD Operations ──────────────────────────────────────────────────
  getAll(): Observable<{cls}[]> {{
    return this.http.get<{cls}[]>(this.baseUrl).pipe(
      retry(1),
      catchError(this.handleError<{cls}[]>('getAll', []))
    );
  }}

  getById(id: number): Observable<{cls}> {{
    return this.http.get<{cls}>(`${{this.baseUrl}}/${{id}}`).pipe(
      catchError(this.handleError<{cls}>('getById'))
    );
  }}

  create(dto: {cls}CreateDto): Observable<{cls}> {{
    return this.http.post<{cls}>(this.baseUrl, dto, HTTP_OPTIONS).pipe(
      catchError(this.handleError<{cls}>('create'))
    );
  }}

  update(id: number, dto: {cls}UpdateDto): Observable<{cls}> {{
    return this.http.put<{cls}>(`${{this.baseUrl}}/${{id}}`, dto, HTTP_OPTIONS).pipe(
      catchError(this.handleError<{cls}>('update'))
    );
  }}

  delete(id: number): Observable<void> {{
    return this.http.delete<void>(`${{this.baseUrl}}/${{id}}`, HTTP_OPTIONS).pipe(
      catchError(this.handleError<void>('delete'))
    );
  }}
{"".join(fk_loaders)}

  // ── Error Handler ────────────────────────────────────────────────────
  private handleError<T>(operation = 'operation', result?: T) {{
    return (error: HttpErrorResponse): Observable<T> => {{
      console.error(`[${{operation}}] error:`, error);
      if (error.status === 0) {{
        throw new Error('Network error — please check your connection.');
      }} else if (error.status === 404) {{
        throw new Error('Resource not found.');
      }} else if (error.status === 409) {{
        throw new Error('Conflict — record already exists.');
      }} else {{
        throw new Error(error.error?.message || `Server error ${{error.status}}`);
      }}
    }};
  }}
}}
"""

    # ── Component TS ─────────────────────────────────────────────────────────
    def _component_ts(self, table: str, tbl: dict) -> str:
        cls   = to_pascal(table)
        kebab = to_kebab(table)
        camel = to_camel(table)
        pk    = next((f for f in tbl["fields"] if f["is_pk"]), tbl["fields"][0])
        non_pk_fields = [f for f in tbl["fields"] if not f["is_identity"]]

        fk_vars    = []
        fk_load    = []
        fk_imports = []
        for fk in tbl["foreign_keys"]:
            ref_cls  = to_pascal(fk["ref_table"])
            ref_keb  = to_kebab(fk["ref_table"])
            ref_caml = to_camel(fk["ref_table"])
            fk_imports.append(f"import {{ {ref_cls} }} from '../{ref_keb}/{ref_keb}.model';")
            fk_vars.append(f"  {ref_caml}List: {ref_cls}[] = [];")
            fk_load.append(f"""    this.{camel}Service.get{ref_cls}List().subscribe({{
      next: data => this.{ref_caml}List = data,
      error: err => this.showError(err.message)
    }});""")

        # Build reactive-form validators
        form_controls = []
        for f in non_pk_fields:
            validators = []
            if f["required"]:
                validators.append("Validators.required")
            if f["max_len"]:
                validators.append(f"Validators.maxLength({f['max_len']})")
            if f["db_type"] in ("int","bigint","smallint","tinyint","decimal","numeric","float"):
                validators.append("Validators.pattern(/^-?\\d+(\\.\\d+)?$/)")
            vstr = f"[null, [{', '.join(validators)}]]" if validators else "[null]"
            form_controls.append(f"      {f['name']}: {vstr},")

        return f"""// Auto-generated component for {table}
import {{ Component, OnInit, OnDestroy }} from '@angular/core';
import {{ FormBuilder, FormGroup, Validators, AbstractControl }} from '@angular/forms';
import {{ Subject }} from 'rxjs';
import {{ takeUntil }} from 'rxjs/operators';
import {{ {cls}Service }} from './{kebab}.service';
import {{ {cls}, {cls}CreateDto }} from './{kebab}.model';
{"".join(fk_imports)}

@Component({{
  selector: 'app-{kebab}',
  templateUrl: './{kebab}.component.html',
  styleUrls: ['./{kebab}.component.css']
}})
export class {cls}Component implements OnInit, OnDestroy {{

  // ── State ──────────────────────────────────────────────────────────────
  records: {cls}[] = [];
  filteredRecords: {cls}[] = [];
  form!: FormGroup;
  isLoading = false;
  isSubmitting = false;
  editMode = false;
  selectedId: number | null = null;
  errorMessage = '';
  successMessage = '';
  searchTerm = '';
  showDeleteConfirm = false;
  deleteTargetId: number | null = null;
  private destroy$ = new Subject<void>();

  // ── FK lookup lists ────────────────────────────────────────────────────
{"".join(fk_vars)}

  constructor(
    private fb: FormBuilder,
    private {camel}Service: {cls}Service
  ) {{}}

  ngOnInit(): void {{
    this.buildForm();
    this.loadAll();
{chr(10).join(fk_load)}
  }}

  ngOnDestroy(): void {{
    this.destroy$.next();
    this.destroy$.complete();
  }}

  // ── Form ───────────────────────────────────────────────────────────────
  buildForm(): void {{
    this.form = this.fb.group({{
{chr(10).join(form_controls)}
    }});
  }}

  get f(): {{ [key: string]: AbstractControl }} {{
    return this.form.controls;
  }}

  // ── Load ───────────────────────────────────────────────────────────────
  loadAll(): void {{
    this.isLoading = true;
    this.clearMessages();
    this.{camel}Service.getAll()
      .pipe(takeUntil(this.destroy$))
      .subscribe({{
        next:  data  => {{ this.records = data; this.applyFilter(); this.isLoading = false; }},
        error: err   => {{ this.showError(err.message); this.isLoading = false; }}
      }});
  }}

  applyFilter(): void {{
    const term = this.searchTerm.toLowerCase();
    this.filteredRecords = term
      ? this.records.filter(r => Object.values(r).some(v => String(v).toLowerCase().includes(term)))
      : [...this.records];
  }}

  onSearch(event: Event): void {{
    this.searchTerm = (event.target as HTMLInputElement).value;
    this.applyFilter();
  }}

  // ── CRUD ───────────────────────────────────────────────────────────────
  onSubmit(): void {{
    if (this.form.invalid) {{
      this.form.markAllAsTouched();
      this.showError('Please fix all validation errors before submitting.');
      return;
    }}
    this.isSubmitting = true;
    this.clearMessages();
    const dto = this.form.value as {cls}CreateDto;

    const op = this.editMode && this.selectedId !== null
      ? this.{camel}Service.update(this.selectedId, {{ ...dto, {pk['name']}: this.selectedId }})
      : this.{camel}Service.create(dto);

    op.pipe(takeUntil(this.destroy$)).subscribe({{
      next: () => {{
        this.showSuccess(this.editMode ? 'Record updated.' : 'Record created.');
        this.resetForm();
        this.loadAll();
        this.isSubmitting = false;
      }},
      error: err => {{ this.showError(err.message); this.isSubmitting = false; }}
    }});
  }}

  onEdit(record: {cls}): void {{
    this.editMode  = true;
    this.selectedId = (record as any)['{pk["name"]}'];
    this.form.patchValue(record);
    this.clearMessages();
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
  }}

  onDeleteRequest(id: number): void {{
    this.deleteTargetId = id;
    this.showDeleteConfirm = true;
  }}

  onDeleteConfirm(): void {{
    if (this.deleteTargetId === null) return;
    this.isLoading = true;
    this.{camel}Service.delete(this.deleteTargetId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({{
        next: () => {{
          this.showSuccess('Record deleted.');
          this.loadAll();
          this.showDeleteConfirm = false;
          this.isLoading = false;
        }},
        error: err => {{ this.showError(err.message); this.isLoading = false; this.showDeleteConfirm = false; }}
      }});
  }}

  onDeleteCancel(): void {{
    this.showDeleteConfirm = false;
    this.deleteTargetId = null;
  }}

  resetForm(): void {{
    this.form.reset();
    this.editMode   = false;
    this.selectedId = null;
    this.clearMessages();
  }}

  // ── Helpers ────────────────────────────────────────────────────────────
  showError(msg: string): void {{
    this.errorMessage   = msg;
    this.successMessage = '';
  }}

  showSuccess(msg: string): void {{
    this.successMessage = msg;
    this.errorMessage   = '';
    setTimeout(() => this.successMessage = '', 4000);
  }}

  clearMessages(): void {{
    this.errorMessage   = '';
    this.successMessage = '';
  }}

  isFieldInvalid(name: string): boolean {{
    const ctrl = this.f[name];
    return !!ctrl && ctrl.invalid && (ctrl.dirty || ctrl.touched);
  }}

  getErrorMsg(name: string, label: string): string {{
    const ctrl = this.f[name];
    if (!ctrl) return '';
    if (ctrl.hasError('required'))   return `${{label}} is required.`;
    if (ctrl.hasError('maxlength'))  return `${{label}} exceeds maximum length.`;
    if (ctrl.hasError('pattern'))    return `${{label}} must be a valid number.`;
    return '';
  }}
}}
"""

    # ── Component HTML ────────────────────────────────────────────────────────
    def _component_html(self, table: str, tbl: dict) -> str:
        cls      = to_pascal(table)
        camel    = to_camel(table)
        kebab    = to_kebab(table)
        pk       = next((f for f in tbl["fields"] if f["is_pk"]), tbl["fields"][0])
        fk_cols  = {fk["column"]: fk for fk in tbl["foreign_keys"]}
        non_pk   = [f for f in tbl["fields"] if not f["is_identity"]]

        # Build form fields HTML
        form_fields = []
        for f in non_pk:
            label  = f["name"].replace("_"," ").title()
            err_id = f"err_{f['name']}"

            if f["name"] in fk_cols:
                fk        = fk_cols[f["name"]]
                ref_tbl   = fk["ref_table"]
                ref_col   = fk["ref_column"]
                ref_camel = to_camel(ref_tbl)
                # determine display field (second field of ref table)
                ref_fields = self.schema.get(ref_tbl, {}).get("fields", [])
                disp_field = ref_fields[1]["name"] if len(ref_fields) > 1 else ref_col
                field_html = f"""
    <div class="form-group">
      <label for="{f['name']}">{label} *</label>
      <select id="{f['name']}" formControlName="{f['name']}"
              [class.invalid]="isFieldInvalid('{f['name']}')">
        <option value="">-- Select {label} --</option>
        <option *ngFor="let item of {ref_camel}List" [value]="item.{ref_col}">
          {{{{ item.{disp_field} }}}}
        </option>
      </select>
      <span class="error-msg" *ngIf="isFieldInvalid('{f['name']}')">
        {{{{ getErrorMsg('{f['name']}', '{label}') }}}}
      </span>
    </div>"""
            elif f["html_input"] == "textarea":
                req_star = " *" if f["required"] else ""
                field_html = f"""
    <div class="form-group">
      <label for="{f['name']}">{label}{req_star}</label>
      <textarea id="{f['name']}" formControlName="{f['name']}" rows="3"
                [class.invalid]="isFieldInvalid('{f['name']}')"></textarea>
      <span class="error-msg" *ngIf="isFieldInvalid('{f['name']}')">
        {{{{ getErrorMsg('{f['name']}', '{label}') }}}}
      </span>
    </div>"""
            elif f["html_input"] == "checkbox":
                field_html = f"""
    <div class="form-group form-check">
      <input type="checkbox" id="{f['name']}" formControlName="{f['name']}">
      <label for="{f['name']}">{label}</label>
    </div>"""
            else:
                req_star   = " *" if f["required"] else ""
                max_attr   = f' maxlength="{f["max_len"]}"' if f["max_len"] else ""
                field_html = f"""
    <div class="form-group">
      <label for="{f['name']}">{label}{req_star}</label>
      <input id="{f['name']}" type="{f['html_input']}" formControlName="{f['name']}"
             [class.invalid]="isFieldInvalid('{f['name']}')"{max_attr}>
      <span class="error-msg" *ngIf="isFieldInvalid('{f['name']}')">
        {{{{ getErrorMsg('{f['name']}', '{label}') }}}}
      </span>
    </div>"""
            form_fields.append(field_html)

        # Table header columns
        header_cols = "".join(
            f'\n        <th>{f["name"].replace("_"," ").title()}</th>'
            for f in tbl["fields"]
        )

        # Table data columns
        data_cols = "".join(
            f'\n        <td>{{{{ record.{f["name"]} }}}}</td>'
            for f in tbl["fields"]
        )

        return f"""<!-- Auto-generated component template for {table} -->
<div class="page-wrapper">
  <div class="page-header">
    <h2>{{ '{cls}' }} Management</h2>
    <p class="subtitle">Manage all {table.replace('_',' ')} records</p>
  </div>

  <!-- Alerts -->
  <div class="alert alert-error"   *ngIf="errorMessage">⚠ {{{{ errorMessage }}}}</div>
  <div class="alert alert-success" *ngIf="successMessage">✓ {{{{ successMessage }}}}</div>

  <!-- Form Card -->
  <div class="card">
    <h3>{{{{ editMode ? 'Edit Record' : 'Add New Record' }}}}</h3>
    <form [formGroup]="form" (ngSubmit)="onSubmit()" novalidate>
      <div class="form-grid">
{"".join(form_fields)}
      </div>
      <div class="form-actions">
        <button type="submit" class="btn btn-primary" [disabled]="isSubmitting">
          <span *ngIf="isSubmitting" class="spinner"></span>
          {{{{ editMode ? 'Update' : 'Save' }}}}
        </button>
        <button type="button" class="btn btn-secondary" (click)="resetForm()">Cancel</button>
      </div>
    </form>
  </div>

  <!-- Search + Table -->
  <div class="card table-card">
    <div class="table-toolbar">
      <h3>Records</h3>
      <div class="search-box">
        <input type="text" placeholder="Search records…" (input)="onSearch($event)">
      </div>
      <button class="btn btn-outline" (click)="loadAll()">🔄 Refresh</button>
    </div>

    <div class="loading-overlay" *ngIf="isLoading">
      <div class="spinner large"></div>
    </div>

    <div class="table-scroll" *ngIf="!isLoading">
      <table *ngIf="filteredRecords.length; else noData">
        <thead>
          <tr>{header_cols}
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let record of filteredRecords">
            {data_cols}
            <td class="actions">
              <button class="btn btn-sm btn-edit" (click)="onEdit(record)">✏ Edit</button>
              <button class="btn btn-sm btn-delete"
                      (click)="onDeleteRequest(record.{pk['name']})">🗑 Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
      <ng-template #noData>
        <div class="empty-state">No records found.</div>
      </ng-template>
    </div>
  </div>

  <!-- Delete Confirm Modal -->
  <div class="modal-overlay" *ngIf="showDeleteConfirm">
    <div class="modal">
      <h3>Confirm Delete</h3>
      <p>Are you sure you want to delete this record? This cannot be undone.</p>
      <div class="modal-actions">
        <button class="btn btn-danger"     (click)="onDeleteConfirm()">Delete</button>
        <button class="btn btn-secondary"  (click)="onDeleteCancel()">Cancel</button>
      </div>
    </div>
  </div>
</div>
"""

    # ── Component CSS ────────────────────────────────────────────────────────
    def _component_css(self) -> str:
        return """.page-wrapper { max-width: 1200px; margin: 0 auto; padding: 1.5rem; font-family: 'Inter', sans-serif; }
.page-header { margin-bottom: 1.5rem; }
.page-header h2 { font-size: 1.6rem; color: #1e3a5f; margin: 0; }
.page-header .subtitle { color: #64748b; margin: 0.2rem 0 0; }

.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
.card h3 { font-size: 1rem; color: #1e293b; margin: 0 0 1rem; }

.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1rem; }
.form-group { display: flex; flex-direction: column; }
.form-group label { font-size: 0.82rem; font-weight: 600; color: #475569; margin-bottom: 4px; }
.form-group input, .form-group select, .form-group textarea {
  padding: 8px 12px; border: 1.5px solid #cbd5e1; border-radius: 7px;
  font-size: 0.9rem; outline: none; transition: border .2s;
}
.form-group input:focus, .form-group select:focus, .form-group textarea:focus { border-color: #3b82f6; }
.form-group input.invalid, .form-group select.invalid, .form-group textarea.invalid { border-color: #ef4444; }
.error-msg { font-size: 0.75rem; color: #ef4444; margin-top: 3px; }
.form-check { flex-direction: row; align-items: center; gap: 8px; }

.form-actions { margin-top: 1.2rem; display: flex; gap: 0.7rem; }

.btn { padding: 8px 20px; border-radius: 8px; font-weight: 600; font-size: 0.87rem; cursor: pointer; border: none; transition: all .15s; }
.btn-primary { background: #2563eb; color: #fff; } .btn-primary:hover { background: #1d4ed8; }
.btn-secondary { background: #e2e8f0; color: #475569; } .btn-secondary:hover { background: #cbd5e1; }
.btn-outline { background: transparent; border: 1.5px solid #cbd5e1; color: #475569; }
.btn-danger { background: #dc2626; color: #fff; } .btn-danger:hover { background: #b91c1c; }
.btn-sm { padding: 4px 12px; font-size: 0.8rem; }
.btn-edit { background: #f0f9ff; color: #0369a1; border: 1px solid #bae6fd; }
.btn-delete { background: #fff5f5; color: #dc2626; border: 1px solid #fecaca; margin-left: 4px; }
.btn:disabled { opacity: .6; cursor: not-allowed; }

.table-toolbar { display: flex; align-items: center; gap: 0.8rem; margin-bottom: 1rem; flex-wrap: wrap; }
.table-toolbar h3 { flex: 1; margin: 0; }
.search-box input { padding: 7px 12px; border: 1.5px solid #e2e8f0; border-radius: 8px; font-size: 0.87rem; min-width: 200px; }
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.87rem; }
thead { background: #f8fafc; }
th { padding: 10px 14px; text-align: left; font-weight: 600; color: #475569; border-bottom: 1.5px solid #e2e8f0; }
td { padding: 10px 14px; border-bottom: 1px solid #f1f5f9; color: #1e293b; }
tr:hover td { background: #f8fafc; }
.actions { white-space: nowrap; }
.empty-state { text-align: center; padding: 2rem; color: #94a3b8; font-size: 0.9rem; }

.loading-overlay { display: flex; justify-content: center; padding: 2rem; }
.spinner { width: 20px; height: 20px; border: 2.5px solid #e2e8f0; border-top-color: #2563eb; border-radius: 50%; animation: spin .6s linear infinite; display: inline-block; margin-right: 6px; }
.spinner.large { width: 36px; height: 36px; }
@keyframes spin { to { transform: rotate(360deg); } }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 12px; padding: 2rem; max-width: 400px; width: 90%; }
.modal h3 { margin: 0 0 0.6rem; color: #1e293b; }
.modal p { color: #64748b; }
.modal-actions { display: flex; gap: 0.7rem; margin-top: 1.2rem; }

.alert { padding: 0.8rem 1.2rem; border-radius: 8px; margin-bottom: 1rem; font-size: 0.9rem; }
.alert-error { background: #fef2f2; border: 1px solid #fecaca; color: #dc2626; }
.alert-success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #16a34a; }
"""

    # ── App Module ────────────────────────────────────────────────────────────
    def _app_module(self, table: str) -> str:
        cls   = to_pascal(table)
        kebab = to_kebab(table)
        return f"""// Auto-generated app.module.ts — add more components as needed
import {{ NgModule }} from '@angular/core';
import {{ BrowserModule }} from '@angular/platform-browser';
import {{ HttpClientModule }} from '@angular/common/http';
import {{ ReactiveFormsModule, FormsModule }} from '@angular/forms';
import {{ AppComponent }} from './app.component';
import {{ {cls}Component }} from './{kebab}/{kebab}.component';

@NgModule({{
  declarations: [AppComponent, {cls}Component],
  imports: [BrowserModule, HttpClientModule, ReactiveFormsModule, FormsModule],
  providers: [],
  bootstrap: [AppComponent]
}})
export class AppModule {{}}
"""

    def _environment(self) -> str:
        return f"""export const environment = {{
  production: false,
  apiUrl: 'http://localhost:8080'
}};
"""
