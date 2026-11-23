export type OrgCategory =
  | "tailor"
  | "shoemaker"
  | "leatherworker"
  | "electrician"
  | "plumber"
  | "carpenter"
  | "mechanic"
  | "welder"
  | "painter"
  | "ac_technician"
  | "mason"
  | "hair_beauty"
  | "caterer"
  | "phone_repair"
  | "generator_tech"
  | "cleaner"
  | "other";

export type AvailabilityStatus = "available" | "busy" | "offline";
export type VerificationStatus = "unsubmitted" | "pending_review" | "approved" | "rejected";
export type GovernmentIdType = "nin_slip" | "voters_card" | "drivers_license" | "intl_passport";
export type VerificationDocumentType =
  | "nin_slip"
  | "cac_certificate"
  | "utility_bill"
  | "trade_certificate"
  | "workshop_photo";
export type EscrowStatus =
  | "awaiting_funding"
  | "funded_held"
  | "work_submitted"
  | "released"
  | "disputed"
  | "refunded"
  | "cancelled";
export type UnitSystem = "cm" | "in";
export type MembershipRole = "owner" | "manager" | "artisan" | "sales_assistant";

export interface NigerianState {
  id: string;
  name: string;
  code: string;
  geopolitical_zone: string;
}

export interface NigerianLGA {
  id: string;
  state: string;
  state_name: string;
  name: string;
  code: string;
}

export interface NigerianWard {
  id: string;
  lga: string;
  lga_name: string;
  state_id: string;
  state_name: string;
  name: string;
  code: string;
}

export interface PollingUnit {
  id: string;
  ward: string;
  ward_name: string;
  lga_id: string;
  lga_name: string;
  state_id: string;
  state_name: string;
  name: string;
  pu_code: string;
  landmark: string;
  latitude: string | null;
  longitude: string | null;
}

export interface LocationSearchResponse {
  wards: NigerianWard[];
  polling_units: PollingUnit[];
}

export interface LocationResolvedResponse {
  state: NigerianState | null;
  lga: NigerianLGA | null;
  ward: NigerianWard | null;
  polling_unit: PollingUnit | null;
  landmark: string;
  match_source: string;
  distance_km: number | null;
  nearby_artisan_count: number;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  category: OrgCategory;
  category_label?: string;
  email: string;
  phone: string;
  address: string;
  city: string;
  country: string;
  state: string | null;
  state_name: string | null;
  lga: string | null;
  lga_name: string | null;
  ward: string | null;
  ward_name: string | null;
  polling_unit: string | null;
  polling_unit_name: string | null;
  polling_unit_code: string | null;
  service_wards: string[];
  service_ward_names: string[];
  landmark: string;
  availability_status: AvailabilityStatus;
  available_for_callout: boolean;
  offers_goods: boolean;
  offers_services: boolean;
  callout_fee: string | null;
  years_experience: number | null;
  skills: string[];
  is_verified: boolean;
  verification_status: VerificationStatus;
  currency: string;
  preferred_unit: UnitSystem;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  role?: MembershipRole | null;
}

export interface MembershipSummary {
  id: string;
  role: MembershipRole;
  status: "active" | "invited" | "suspended";
  organization: Organization;
  created_at: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string;
  state: string | null;
  state_name: string | null;
  lga: string | null;
  lga_name: string | null;
  ward: string | null;
  ward_name: string | null;
  polling_unit: string | null;
  polling_unit_name: string | null;
  polling_unit_code: string | null;
  landmark: string;
  latitude: string | null;
  longitude: string | null;
  is_platform_admin: boolean;
  created_at: string;
  memberships: MembershipSummary[];
}

export interface Customer {
  id: string;
  organization: string;
  full_name: string;
  phone: string;
  email: string;
  address: string;
  preferred_contact_method: "phone" | "whatsapp" | "email" | "sms";
  notes: string;
  is_archived: boolean;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface MeasurementField {
  id: string;
  key: string;
  label: string;
  description: string;
  unit_type: "circumference" | "length" | "width" | "angle" | "numeric" | "text";
  default_unit: "cm" | "in" | "deg" | "none";
  min_value: string | null;
  max_value: string | null;
  is_required: boolean;
  display_order: number;
  guidance_text: string;
}

export interface MeasurementTemplateVersion {
  id: string;
  version_number: number;
  is_published: boolean;
  changelog: string;
  created_at: string;
  fields: MeasurementField[];
}

export interface MeasurementTemplate {
  id: string;
  organization: string | null;
  is_system: boolean;
  name: string;
  slug: string;
  category: "tailoring" | "shoemaking" | "leatherwork" | "other";
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  latest_version: MeasurementTemplateVersion | null;
}

export interface MeasurementValue {
  id: string;
  field: string;
  field_key: string;
  field_label: string;
  unit_type: string;
  display_order: number;
  numeric_value: string | null;
  text_value: string;
  unit: string;
}

export interface MeasurementProfile {
  id: string;
  organization: string;
  customer: string;
  template_version: string;
  template_name: string;
  template_category: string;
  template_version_number: number;
  label: string;
  unit_system: UnitSystem;
  source: "manual" | "customer_submitted" | "camera_assisted" | "imported";
  status: "draft" | "submitted" | "needs_review" | "verified" | "superseded";
  version_number: number;
  parent_profile: string | null;
  is_latest: boolean;
  measured_at: string;
  notes: string;
  created_by: string | null;
  created_by_name: string | null;
  verified_by: string | null;
  verified_by_name: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
  values: MeasurementValue[];
}

export interface MeasurementRequestItem {
  id: string;
  customer: string;
  customer_name: string;
  template_version: string;
  template_name: string;
  status: "pending" | "submitted" | "expired" | "revoked";
  expires_at: string;
  submitted_profile: string | null;
  notes: string;
  created_at: string;
  token?: string;
  public_path?: string;
}

export interface PublicMeasurementRequest {
  organization_name: string;
  customer_first_name: string;
  preferred_unit: UnitSystem;
  template_name: string;
  expires_at: string;
  notes: string;
  fields: MeasurementField[];
}

export interface MeasurementShareLink {
  id: string;
  customer: string;
  customer_name: string;
  profile: string;
  profile_label: string;
  profile_version: number;
  recipient_label: string;
  status: "active" | "revoked" | "expired";
  expires_at: string;
  access_count: number;
  last_accessed_at: string | null;
  created_at: string;
  token?: string;
  public_path?: string;
}

export interface PublicFitPassport {
  issuing_organization: string;
  customer_first_name: string;
  profile_label: string;
  template_name: string;
  template_category: string;
  unit_system: UnitSystem;
  version_number: number;
  verified_at: string | null;
  measured_at: string;
  expires_at: string;
  values: MeasurementValue[];
}

export type MediaViewAngle = "front" | "side" | "back" | "detail";

export interface MediaAsset {
  id: string;
  customer: string;
  profile: string | null;
  measurement_request: string | null;
  view_angle: MediaViewAngle;
  content_type: string;
  file_size_bytes: number;
  quality_metadata: Record<string, unknown>;
  allow_model_training: boolean;
  consent_granted_at: string | null;
  retention_expires_at: string;
  status: "active" | "deleted" | "expired";
  deleted_at: string | null;
  uploaded_by: string | null;
  uploaded_by_name: string | null;
  content_path: string | null;
  created_at: string;
}

export interface MediaAccessLogItem {
  id: string;
  action: "uploaded" | "viewed" | "deleted" | "purged";
  accessed_by: string | null;
  accessed_by_name: string | null;
  ip_address: string | null;
  notes: string;
  created_at: string;
}

export type OrderStatus =
  | "draft"
  | "awaiting_measurements"
  | "quoted"
  | "confirmed"
  | "in_production"
  | "fitting"
  | "ready"
  | "completed"
  | "cancelled"
  | "on_hold";

export interface OrderStatusEvent {
  id: string;
  from_status: string;
  to_status: OrderStatus;
  notes: string;
  changed_by: string | null;
  changed_by_name: string | null;
  created_at: string;
}

export interface OrderSnapshotValue {
  field_key: string;
  field_label: string;
  numeric_value: string | null;
  text_value: string;
  unit: string;
}

export interface MeasurementSnapshot {
  profile_id: string;
  version_number: number;
  label: string;
  template_name: string;
  template_version_number: number;
  unit_system: UnitSystem;
  status: string;
  measured_at: string;
  captured_at: string;
  values: OrderSnapshotValue[];
}

export interface Order {
  id: string;
  order_number: string;
  customer: string;
  customer_name: string;
  garment_type: string;
  status: OrderStatus;
  quoted_amount: string;
  agreed_amount: string | null;
  deposit_amount: string;
  currency: string;
  payment_status: "unpaid" | "partial" | "paid";
  expected_completion_date: string | null;
  assigned_to: string | null;
  assigned_to_name: string | null;
  delivery_method: "pickup" | "delivery" | "shipping";
  measurement_profile: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrderDetail extends Order {
  description: string;
  measurement_snapshot: MeasurementSnapshot | null;
  category_options: Record<string, string>;
  customer_instructions: string;
  internal_notes: string;
  created_by: string | null;
  status_events: OrderStatusEvent[];
  allowed_next_statuses: OrderStatus[];
}

export interface OrganizationMember {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: MembershipRole;
  status: "active" | "invited" | "suspended";
  created_at: string;
}

export interface OrganizationInvitation {
  id: string;
  organization: string;
  email: string;
  role: MembershipRole;
  status: "pending" | "accepted" | "revoked" | "expired";
  expires_at: string;
  invited_by: string | null;
  invited_by_name: string | null;
  accepted_at: string | null;
  created_at: string;
  token?: string;
  invite_path?: string;
}

export interface PublicInvitationDetail {
  organization_name: string;
  organization_category: OrgCategory;
  email: string;
  role: MembershipRole;
  expires_at: string;
  invited_by_name: string | null;
  account_exists: boolean;
}

export type ProductionTaskStage =
  | "cutting"
  | "sewing"
  | "embroidery"
  | "fitting"
  | "alteration"
  | "finishing"
  | "quality_check"
  | "other";

export type ProductionTaskStatus = "todo" | "in_progress" | "blocked" | "done";

export interface ProductionTask {
  id: string;
  organization: string;
  order: string;
  order_number: string;
  title: string;
  stage: ProductionTaskStage;
  status: ProductionTaskStatus;
  is_alteration: boolean;
  assigned_to: string | null;
  assigned_to_name: string | null;
  due_date: string | null;
  notes: string;
  display_order: number;
  completed_at: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductionBoardOrder {
  id: string;
  order_number: string;
  customer: string;
  customer_name: string;
  garment_type: string;
  status: OrderStatus;
  expected_completion_date: string | null;
  assigned_to: string | null;
  assigned_to_name: string | null;
  total_tasks: number;
  completed_tasks: number;
  alteration_tasks: number;
  allowed_next_statuses: OrderStatus[];
}

export interface ProductionBoardColumn {
  status: OrderStatus;
  label: string;
  orders: ProductionBoardOrder[];
}

export interface ProductionBoardResponse {
  columns: ProductionBoardColumn[];
}

export type AppointmentType =
  | "measurement"
  | "first_fitting"
  | "final_fitting"
  | "consultation"
  | "collection"
  | "other";

export type AppointmentStatus = "scheduled" | "completed" | "cancelled" | "no_show";

export interface Appointment {
  id: string;
  organization: string;
  customer: string;
  customer_name: string;
  order: string | null;
  order_number: string | null;
  appointment_type: AppointmentType;
  title: string;
  scheduled_at: string;
  duration_minutes: number;
  location: string;
  status: AppointmentStatus;
  assigned_to: string | null;
  assigned_to_name: string | null;
  notes: string;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface DashboardSummary {
  organization: {
    id: string;
    name: string;
    category: OrgCategory;
    currency: string;
    preferred_unit: UnitSystem;
  };
  metrics: {
    total_customers: number;
    active_orders: number;
    orders_awaiting_measurements: number;
    orders_in_production: number;
    orders_ready: number;
    upcoming_appointments: number;
    monthly_recorded_deposits: string;
  };
  recent_orders: Order[];
  recent_customers: Customer[];
  upcoming_appointments: Appointment[];
}

export type ProductType = "ready_made" | "made_to_order" | "service";
export type ProductStatus = "draft" | "published" | "archived";

export interface ProductVariant {
  id: string;
  product: string;
  name: string;
  sku: string;
  price_override: string | null;
  stock_quantity: number;
  is_active: boolean;
  created_at: string;
}

export interface Product {
  id: string;
  organization: string;
  name: string;
  slug: string;
  description: string;
  category: string;
  product_type: ProductType;
  price: string;
  currency: string;
  image_url: string;
  sku: string;
  status: ProductStatus;
  track_inventory: boolean;
  stock_quantity: number;
  variants: ProductVariant[];
  created_at: string;
  updated_at: string;
}

export type InventoryMovementType =
  | "initial"
  | "restock"
  | "sale"
  | "adjustment"
  | "return"
  | "damage";

export interface InventoryMovement {
  id: string;
  product: string;
  variant: string | null;
  variant_name: string | null;
  movement_type: InventoryMovementType;
  quantity_delta: number;
  balance_after: number;
  reason: string;
  performed_by: string | null;
  performed_by_name: string | null;
  created_at: string;
}

export interface StorefrontSettings {
  id: string;
  organization_name: string;
  slug: string;
  category: OrgCategory;
  category_label: string;
  phone: string;
  city: string;
  country: string;
  currency: string;
  state_id: string | null;
  state_name: string | null;
  lga_id: string | null;
  lga_name: string | null;
  ward_id: string | null;
  ward_name: string | null;
  polling_unit_id: string | null;
  polling_unit_name: string | null;
  polling_unit_code: string | null;
  landmark: string;
  service_ward_names: string[];
  availability_status: AvailabilityStatus;
  available_for_callout: boolean;
  offers_goods: boolean;
  offers_services: boolean;
  callout_fee: string | null;
  years_experience: number | null;
  skills: string[];
  is_verified: boolean;
  verification_status: VerificationStatus;
  cac_verified: boolean;
  headline: string;
  bio: string;
  whatsapp_number: string;
  instagram_handle: string;
  is_published: boolean;
  updated_at: string;
}

export type InquiryStatus = "new" | "contacted" | "converted" | "closed";
export type InquiryType = "work_callout" | "product_order" | "service_booking" | "general";
export type InquiryUrgency = "normal" | "today" | "emergency";

export interface StorefrontInquiry {
  id: string;
  product: string | null;
  product_name: string | null;
  inquiry_type: InquiryType;
  urgency: InquiryUrgency;
  buyer_name: string;
  buyer_phone: string;
  buyer_email: string;
  customer_ward: string | null;
  customer_ward_name: string | null;
  customer_polling_unit: string | null;
  customer_polling_unit_name: string | null;
  customer_polling_unit_code: string | null;
  customer_address: string;
  preferred_date: string | null;
  quantity: number;
  budget_amount: string | null;
  message: string;
  status: InquiryStatus;
  converted_order: string | null;
  converted_order_number: string | null;
  created_at: string;
}

export interface PublicStorefrontResponse {
  storefront: StorefrontSettings;
  products: Product[];
}

export interface NotificationItem {
  id: string;
  organization: string;
  event_type:
    | "measurement_submitted"
    | "order_confirmed"
    | "order_ready"
    | "storefront_inquiry"
    | "low_stock"
    | "system";
  title: string;
  message: string;
  link_path: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  unread_count: number;
  results: NotificationItem[];
}

export interface Plan {
  id: string;
  code: string;
  name: string;
  description: string;
  monthly_price: string;
  currency: string;
  max_members: number;
  max_customers: number;
  max_monthly_measurement_requests: number;
  max_products: number;
  is_active: boolean;
  display_order: number;
}

export interface SubscriptionInfo {
  id: string;
  plan: Plan;
  status: "trialing" | "active" | "past_due" | "cancelled";
  provider: "manual" | "paystack";
  provider_reference: string;
  current_period_start: string;
  current_period_end: string | null;
  trial_ends_at: string | null;
  updated_at: string;
}

export interface UsageCounter {
  used: number;
  limit: number;
}

export interface PaymentTransaction {
  id: string;
  reference: string;
  plan: string | null;
  plan_name: string | null;
  provider: string;
  amount: string;
  currency: string;
  status: "pending" | "succeeded" | "failed" | "refunded";
  verified_at: string | null;
  created_at: string;
}

export interface SubscriptionOverview {
  subscription: SubscriptionInfo;
  usage: {
    members: UsageCounter;
    customers: UsageCounter;
    monthly_measurement_requests: UsageCounter;
    products: UsageCounter;
  };
  transactions: PaymentTransaction[];
  paystack_configured: boolean;
}

export interface AuditLogItem {
  id: string;
  organization: string | null;
  organization_name: string | null;
  actor: string | null;
  actor_email: string | null;
  action: string;
  target_type: string;
  target_id: string;
  reason: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface PlatformAdminOverview {
  total_organizations: number;
  active_organizations: number;
  suspended_organizations: number;
  total_users: number;
  total_customers: number;
  total_orders: number;
}

export interface PlatformAdminLocationSyncStatus {
  state: "idle" | "running" | "succeeded" | "failed";
  mode: string;
  last_message: string;
  error: string;
  started_at: string | null;
  finished_at: string | null;
  total_states: number;
  total_lgas: number;
  total_wards: number;
  total_polling_units: number;
  geolocated_polling_units: number;
  is_full_inec_loaded: boolean;
}

export interface PlatformAdminOrgSummary {
  id: string;
  name: string;
  slug: string;
  category: OrgCategory;
  currency: string;
  is_active: boolean;
  plan_code: string;
  plan_name: string;
  subscription_status: string;
  member_count: number;
  customer_count: number;
  order_count: number;
  created_at: string;
}

export type ProximityTier =
  | "same_polling_unit"
  | "same_ward"
  | "covers_ward"
  | "same_lga"
  | "same_state"
  | "national";

export interface MarketplaceStorefrontCard {
  organization_name: string;
  slug: string;
  category: OrgCategory;
  category_label: string;
  phone: string;
  whatsapp_number: string;
  instagram_handle: string;
  city: string;
  country: string;
  state_id: string | null;
  state_name: string | null;
  lga_id: string | null;
  lga_name: string | null;
  ward_id: string | null;
  ward_name: string | null;
  polling_unit_id: string | null;
  polling_unit_name: string | null;
  polling_unit_code: string | null;
  landmark: string;
  service_ward_names: string[];
  headline: string;
  bio: string;
  skills: string[];
  availability_status: AvailabilityStatus;
  available_for_callout: boolean;
  offers_goods: boolean;
  offers_services: boolean;
  callout_fee: string | null;
  currency: string;
  years_experience: number | null;
  is_verified: boolean;
  verification_status: VerificationStatus;
  cac_verified: boolean;
  published_product_count: number;
  published_service_count: number;
  proximity_tier: ProximityTier | null;
  proximity_label: string | null;
  distance_km: number | null;
}

export interface MarketplaceProductCard extends Product {
  organization_name: string;
  storefront_slug: string;
  organization_category: OrgCategory;
  organization_category_label: string;
  organization_city: string;
  organization_phone: string;
  whatsapp_number: string;
  state_name: string | null;
  lga_name: string | null;
  ward_name: string | null;
  polling_unit_name: string | null;
  proximity_tier: ProximityTier | null;
  proximity_label: string | null;
  distance_km: number | null;
}

export interface MarketplaceCategoryCount {
  code: OrgCategory;
  label: string;
  artisan_count: number;
}

export interface AnalyticsOverview {
  currency: string;
  months: number;
  order_status_breakdown: Array<{ status: string; count: number }>;
  monthly_revenue_trend: Array<{
    month: string;
    orders_count: number;
    quoted_total: string;
    deposits_collected: string;
  }>;
  top_garment_types: Array<{
    garment_type: string;
    count: number;
    quoted_total: string;
  }>;
  production: {
    total_tasks: number;
    completed_tasks: number;
    completion_rate_pct: number;
    open_alterations: number;
  };
  measurements: {
    total_profiles: number;
    verified_profiles: number;
    manual_profiles: number;
    customer_submitted_profiles: number;
    imported_profiles: number;
    active_share_links: number;
  };
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface VerificationDocument {
  id: string;
  document_type: VerificationDocumentType;
  document_type_label: string;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
  uploaded_by_name: string | null;
  content_path: string;
  created_at: string;
}

export interface ArtisanVerification {
  id: string;
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  organization_category: string;
  state_name: string | null;
  ward_name: string | null;
  polling_unit_name: string | null;
  nin_masked: string;
  nin_last4: string;
  government_id_type: GovernmentIdType;
  government_id_type_label: string;
  cac_number: string;
  cac_business_name: string;
  guarantor_name: string;
  guarantor_phone: string;
  bank_name: string;
  bank_account_number: string;
  bank_account_name: string;
  status: VerificationStatus;
  submitted_by_email: string | null;
  submitted_at: string;
  reviewed_by_email: string | null;
  reviewed_at: string | null;
  rejection_reason: string;
  review_notes: string;
  documents: VerificationDocument[];
  created_at: string;
  updated_at: string;
}

export interface OrganizationVerificationResponse {
  status: VerificationStatus;
  submitted: boolean;
  verification: ArtisanVerification | null;
}

export interface EscrowEvent {
  id: string;
  event_type: string;
  from_status: string;
  to_status: EscrowStatus;
  notes: string;
  actor: string | null;
  actor_name: string | null;
  created_at: string;
}

export interface EscrowTransaction {
  id: string;
  reference: string;
  organization: string;
  organization_name: string;
  organization_slug: string;
  organization_category_label: string;
  organization_phone: string;
  organization_is_verified: boolean;
  customer_user: string;
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  order: string | null;
  order_number: string | null;
  inquiry: string | null;
  job_title: string;
  job_description: string;
  total_amount: string;
  materials_advance_pct: number;
  materials_advance_amount: string;
  held_in_escrow_amount: string;
  platform_fee_amount: string;
  artisan_payout_amount: string;
  currency: string;
  status: EscrowStatus;
  payment_provider: string;
  artisan_completion_notes: string;
  dispute_reason: string;
  resolution_notes: string;
  funded_at: string | null;
  work_submitted_at: string | null;
  released_at: string | null;
  disputed_at: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  viewer_role: "customer" | "artisan" | "admin" | "guest";
  events: EscrowEvent[];
}

export interface EscrowFundResponse {
  escrow: EscrowTransaction;
  completion_pin: string;
  detail: string;
}
