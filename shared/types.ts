// SIH26034 — Shared TypeScript types
// One-to-one with backend Pydantic schemas. Field names match the API JSON keys.

// ---- Enums ----

export type VerificationState =
  | "SATISFIED"
  | "VIOLATION"
  | "NOT_VERIFIED"
  | "CONFLICT"
  | "NOT_APPLICABLE";

export type EvidenceSourceType =
  | "OCR"
  | "BARCODE"
  | "QR"
  | "PRODUCT_DATABASE"
  | "MANUAL_ENTRY"
  | "OFFICER_CORRECTION"
  | "PRIOR_RECORD";

export type OfficerRole = "ADMIN" | "INSPECTOR" | "VIEWER";

export type ScanStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";

// ---- Geometry ----

export interface BBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

// ---- Evidence ----

export interface Evidence {
  id: string; // UUID
  source_type: EvidenceSourceType;
  raw_text: string | null;
  confidence: number;
  image_id: string | null;
  bbox: BBox | null;
  preprocessing_variant: string | null;
  extracted_at: string; // datetime
}

// ---- Declaration ----

export interface OfficerCorrection {
  officer_id: string;
  corrected_value: unknown;
  reason: string;
  corrected_at: string;
}

export interface Declaration {
  id: string;
  scan_id: string;
  field_name: string;
  extracted_value: unknown;
  evidence: Evidence[];
  rule_id: string | null;
  verdict: VerificationState;
  reason: string;
  confidence: number;
  officer_correction: OfficerCorrection | null;
}

// ---- Product sub-models ----

export interface Quantity {
  value: number;
  unit: string;
}

export interface MRP {
  amount: number;
  currency: string;
}

export interface UnitSalePrice {
  amount: number;
  currency: string;
}

export interface Barcode {
  code: string;
  format: string;
}

export interface Dates {
  manufacture: string | null;
  best_before: string | null;
  use_by: string | null;
}

// ---- CanonicalProduct ----

export interface CanonicalProduct {
  id: string;
  identity: string | null;
  brand: string | null;
  category: string | null;
  manufacturer: string | null;
  packer: string | null;
  importer: string | null;
  country_of_origin: string | null;
  quantity: Quantity | null;
  mrp: MRP | null;
  dates: Dates;
  consumer_care: string | null;
  unit_sale_price: UnitSalePrice | null;
  barcode: Barcode | null;
  declarations: Declaration[];
  evidence: Evidence[];
  created_at: string;
  updated_at: string;
}

// ---- Scan ----

export interface ImageInfo {
  id: string;
  url: string;
  uploaded_at: string;
}

export interface ImageQuality {
  blur: string;
  glare: string;
  perspective: string;
  resolution: string;
  recommended_action: string;
}

export interface Scan {
  id: string;
  product_id: string | null;
  status: ScanStatus;
  images: ImageInfo[];
  image_quality: ImageQuality | null;
  compliance_results: Declaration[];
  overall_status: VerificationState | null;
  warnings: string[];
  created_at: string;
}

// ---- Rule / RuleSet ----

export interface Rule {
  rule_id: string;
  source_document: string;
  clause: string;
  applicability: string;
  required_declaration: string;
  validation_conditions: unknown;
  measurement_requirements: unknown | null;
  exceptions: string[];
  effective_date: string;
  evidence_requirements: string[];
}

export interface RuleSet {
  id: string;
  source: string;
  rule_version: string;
  effective_from: string;
  effective_to: string | null;
  jurisdiction: string;
  rules: Rule[];
}

// ---- Officer ----

export interface Officer {
  id: string;
  name: string;
  email: string;
  role: OfficerRole;
  created_at: string;
}

// ---- Inspection ----

export interface InspectionAction {
  declaration_id: string;
  action: "confirm" | "correct" | "mark_unresolved";
  old_value: unknown;
  new_value: unknown | null;
  reason: string;
}

export interface Inspection {
  id: string;
  scan_id: string;
  officer_id: string;
  actions: InspectionAction[];
  notes: string | null;
  created_at: string;
}

// ---- API request / response helpers ----

export interface ScanCreateResponse {
  scan_id: string;
  status: ScanStatus;
}

export interface ImageUploadResponse {
  image_id: string;
}

export interface ScanEvidenceGroup {
  declaration_id: string;
  field_name: string;
  evidence: Evidence[];
}

export interface ScanComplianceResponse {
  declarations: Declaration[];
  overall_status: VerificationState | null;
}

export interface DashboardResponse {
  total_scans: number;
  violations: number;
  not_verified_rate: number;
  recent_inspections: Inspection[];
}

export interface AuthLoginRequest {
  email: string;
  password: string;
}

export interface AuthLoginResponse {
  token: string;
  officer: { id: string; role: OfficerRole };
}
