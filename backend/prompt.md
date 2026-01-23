workflow : 
Step 0 — Precondition

Supabase Storage bucket: pdfs

Backend has Supabase service key (server-only) to upload PDF and write DB rows.

Step 1 — Email ingestion → Storage → invoices

Poll mailbox (Microsoft Graph / Gmail / IMAP).

For each email with invoice PDF attachment:

Upload PDF to pdfs bucket at:

storage_path = "YYYY/MM/<source_message_id>.pdf" (or any deterministic path)

Insert into invoices:

source_message_id = provider message id (must be stable/unique)

storage_bucket='pdfs', storage_path=...

status='received'

Insert audit rows:

EMAIL_INGESTED on invoice

PDF_STORED on invoice

Idempotency rule

If source_message_id already exists (unique), skip insertion and skip duplicate processing.

Step 2 — PDF parse (logo + text) → LLM → invoices + invoice_lines

Download PDF from bucket using storage_path.

Extract:

logo_image: first page top area (or best candidate) as PNG/JPG

raw_text: pdf text extraction (and optionally table extraction)

Call OpenAI with:

logo_image + raw_text + strict JSON schema prompt (provided below).

Update invoices (same row):

supplier_name, invoice_number, invoice_date, currency, subtotal_amount, tax_amount, total_amount

status='parsed'

parsed_at=now()

Replace invoice lines:

Delete existing invoice_lines for that invoice (simple approach)

Insert new invoice_lines with line_no 1..N

Audit:

INVOICE_PARSED on invoice with details { line_count, model, warnings }

Step 3 — Validation engine (SKU-first) → validation_lines + buying_price_records + audit
For each invoice_line:

Determine matching key in priority:

If sku exists: match on (supplier_name, sku)

Else: match on (supplier_name, product_name) using case-insensitive exact match first (you can add fuzzy later)

Query buying_price_records candidates:

status='active'

valid_from/valid_to may be ignored initially, or applied if invoice_date is present:

valid if (valid_from is null or valid_from <= invoice_date) and (valid_to is null or invoice_date <= valid_to)

Outcomes:

MATCH: one clear candidate, unit_price == expected_unit_price

Insert validation_lines(status='match', buying_price_record_id=..., expected_unit_price=..., diff_unit_price=0)

MISMATCH: one clear candidate but unit_price != expected_unit_price

Insert validation_lines(status='mismatch', expected_unit_price, diff_unit_price)

Insert audit_log(action='PRICE_MISMATCH', entity_type='invoice_line', details={expected, got, sku, product_name})

NO MATCH (create record): no candidate found AND invoice line has enough data (supplier_name + (sku or product_name) + currency + unit_price)

Insert into buying_price_records:

supplier_name = invoices.supplier_name

sku = invoice_lines.sku

product_name = invoice_lines.product_name

currency = coalesce(line.currency, invoice.currency)

unit_price = invoice_lines.unit_price

status = 'need_review'

source = 'learned_from_invoice'

valid_from = invoice.invoice_date (or null if missing)

Insert validation_lines(status='created_price_record', buying_price_record_id=<new_id>, expected_unit_price=<new_unit_price>, diff_unit_price=null)

Audit PRICE_RECORD_CREATED on buying_price_record

NO MATCH (cannot create): missing critical data (e.g., no sku and no product_name, or no unit_price)

Insert validation_lines(status='no_match', reason='missing sku/product_name or unit_price')

Audit MARKED_NEED_REVIEW on invoice

After all lines:

If any validation_lines.status in ('mismatch','created_price_record','no_match'):

Set invoice status='needs_review'

Else:

Set invoice status='validated'

Set validated_at=now()

Audit INVOICE_VALIDATED on invoice with summary counts

Future scalability hooks (without new tables yet)

Put review actions and outcomes in audit_log.details (e.g., {resolution: "accepted_invoice_price", approved_by: ..., at: ...}).

Add minimal RBAC later via Supabase Auth + RLS on these same tables (no schema change required).



---------------


begin;

-- =========================
-- Extensions
-- =========================
create extension if not exists pgcrypto;
create extension if not exists citext;

-- =========================
-- Enums (minimal)
-- =========================
do $$ begin
  create type public.invoice_status as enum (
    'received',        -- email ingested + pdf stored
    'parsed',          -- LLM extracted header + lines stored
    'validated',       -- validation completed, no issues
    'needs_review',    -- mismatch and/or created price record needs review
    'closed'           -- finished/archived
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.buying_price_status as enum (
    'active',          -- usable for automatic validation
    'need_review',     -- created from invoice or ambiguous match
    'inactive'         -- historical/disabled
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.validation_status as enum (
    'match',
    'mismatch',
    'created_price_record',  -- no match found; we inserted buying_price_records(need_review)
    'no_match'               -- cannot match (e.g., missing sku and weak product name)
  );
exception when duplicate_object then null; end $$;

-- =========================
-- invoices (header + storage pointer)
-- =========================
create table if not exists public.invoices (
  id uuid primary key default gen_random_uuid(),

  -- Email ingestion (idempotency)
  source_provider text not null default 'microsoft365',
  source_mailbox citext null,
  source_message_id text not null unique,
  source_received_at timestamptz null,

  -- Storage pointer (Supabase Storage bucket)
  storage_bucket text not null default 'pdfs',
  storage_path text not null,  -- e.g. "2026/01/<message_id>.pdf"

  -- Parsed header fields (LLM output)
  supplier_name text null,
  invoice_number text null,
  invoice_date date null,
  currency char(3) null,
  subtotal_amount numeric(12,2) null,
  tax_amount numeric(12,2) null,
  total_amount numeric(12,2) null,

  status public.invoice_status not null default 'received',

  parsed_at timestamptz null,
  validated_at timestamptz null,

  created_at timestamptz not null default now(),
  created_by uuid null default auth.uid()
);

create index if not exists invoices_status_idx on public.invoices(status);
create index if not exists invoices_supplier_date_idx on public.invoices(supplier_name, invoice_date);
create index if not exists invoices_invoice_number_idx on public.invoices(invoice_number);

-- =========================
-- invoice_lines (from LLM; keep simple)
-- =========================
create table if not exists public.invoice_lines (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references public.invoices(id) on delete cascade,

  line_no int not null,

  sku text null,                 -- preferred key for matching
  product_name text null,         -- fallback matching key
  description text null,

  quantity numeric(12,3) null check (quantity is null or quantity >= 0),
  unit_price numeric(12,4) null check (unit_price is null or unit_price >= 0),
  line_total numeric(12,2) null check (line_total is null or line_total >= 0),
  currency char(3) null,

  created_at timestamptz not null default now(),
  created_by uuid null default auth.uid(),

  unique (invoice_id, line_no)
);

create index if not exists invoice_lines_invoice_idx on public.invoice_lines(invoice_id);
create index if not exists invoice_lines_sku_idx on public.invoice_lines(sku);
create index if not exists invoice_lines_product_name_idx on public.invoice_lines(lower(product_name));

-- =========================
-- buying_price_records (single source of truth for expected prices)
-- =========================
create table if not exists public.buying_price_records (
  id uuid primary key default gen_random_uuid(),

  supplier_name text not null,
  sku text null,
  product_name text null,

  currency char(3) not null,
  unit_price numeric(12,4) not null check (unit_price >= 0),

  status public.buying_price_status not null default 'active',

  valid_from date null,
  valid_to date null,

  source text not null default 'import',  -- 'import' | 'learned_from_invoice'
  note text null,

  created_at timestamptz not null default now(),
  created_by uuid null default auth.uid()
);

create index if not exists buying_price_supplier_sku_idx
  on public.buying_price_records (supplier_name, sku, status);

create index if not exists buying_price_supplier_product_idx
  on public.buying_price_records (supplier_name, lower(product_name), status);

create index if not exists buying_price_validity_idx
  on public.buying_price_records (valid_from, valid_to);

-- =========================
-- validation_lines (result of validation for each invoice line)
-- =========================
create table if not exists public.validation_lines (
  id uuid primary key default gen_random_uuid(),

  invoice_line_id uuid not null references public.invoice_lines(id) on delete cascade,

  -- what we matched against (nullable when no_match)
  buying_price_record_id uuid null references public.buying_price_records(id) on delete restrict,

  status public.validation_status not null,

  expected_unit_price numeric(12,4) null,
  diff_unit_price numeric(12,4) null,

  reason text null,     -- short human-readable reason
  details jsonb null,   -- optional: match strategy, candidates, etc.

  created_at timestamptz not null default now(),
  created_by uuid null default auth.uid()
);

create index if not exists validation_lines_status_idx on public.validation_lines(status);
create index if not exists validation_lines_invoice_line_idx on public.validation_lines(invoice_line_id);

-- =========================
-- audit_log (append-only actions)
-- =========================
create table if not exists public.audit_log (
  id uuid primary key default gen_random_uuid(),

  entity_type text not null,  -- 'invoice' | 'invoice_line' | 'buying_price_record' | 'validation_line'
  entity_id uuid not null,

  action text not null,       -- 'EMAIL_INGESTED' | 'PDF_STORED' | 'INVOICE_PARSED' | 'PRICE_MISMATCH' | 'PRICE_RECORD_CREATED' | 'MARKED_NEED_REVIEW' | 'RESOLVED' ...
  details jsonb null,

  performed_by uuid null default auth.uid(),
  performed_at timestamptz not null default now()
);

create index if not exists audit_entity_idx on public.audit_log(entity_type, entity_id);
create index if not exists audit_time_idx on public.audit_log(performed_at desc);

commit;
