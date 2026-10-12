-- Initial assignment schema. UUID IDs were verified canonical across all 660,622 source rows.
-- SHA-256 digests use bytea; encode(digest, hex) reconstructs the original hash value.
-- Normalize exact text and configuration rather than storing repeated full quotes/prompts.
begin;
create table if not exists public.pipeline_datasets (
  id bigint generated always as identity primary key,
  name text unique not null, source_sha256 text not null,
  source_rows integer not null, completed_rows integer not null default 0,
  empty_rows integer not null default 0, published boolean not null default false
);
create table if not exists public.review_texts (
  id bigint generated always as identity primary key,
  text_sha256 bytea unique not null check(octet_length(text_sha256)=32), review_text text not null
);
create table if not exists public.label_configs (
  id integer generated always as identity primary key,
  label_config text unique not null, configuration jsonb not null
);
create table if not exists public.processed_reviews (
  dataset_id bigint not null references public.pipeline_datasets(id),
  review_id uuid not null, source_sha256 bytea not null check(octet_length(source_sha256)=32),
  text_id bigint not null references public.review_texts(id),
  review_rating text not null, review_likes text not null,
  app_version text not null, review_timestamp text not null,
  status text not null check(status in ('completed','quarantined')),
  reason text, topic text check(topic in ('access','usability','playback','downloads','catalog','billing','support','other')),
  intent text check(intent in ('cancellation','complaint','request','praise','unclear')),
  severity smallint check(severity between 1 and 5), sentiment numeric(7,6) check(sentiment between -1 and 1),
  needs_review boolean, entities jsonb, quote_start integer, quote_length integer,
  label_config_id integer references public.label_configs(id), cache_source_id uuid,
  model_request_ids uuid[] not null default array[]::uuid[], severity_provenance text,
  primary key(dataset_id,review_id),
  foreign key(dataset_id,cache_source_id) references public.processed_reviews(dataset_id,review_id) deferrable initially deferred,
  check((status='completed' and topic is not null and intent is not null and severity is not null and sentiment is not null and needs_review is not null and label_config_id is not null and entities is not null and jsonb_typeof(entities)='array' and quote_start is not null and quote_start>=0 and quote_length is not null and quote_length>0)
     or (status='quarantined' and length(reason)>0))
);
create table if not exists public.issue_membership (
  dataset_id bigint not null, issue_id text not null, review_id uuid not null,
  primary key(dataset_id,issue_id,review_id),
  foreign key(dataset_id,review_id) references public.processed_reviews(dataset_id,review_id)
);
create table if not exists public.analysis_outputs (
  dataset_id bigint not null references public.pipeline_datasets(id),
  artifact_kind text not null, artifact_sha256 text not null, value jsonb not null,
  primary key(dataset_id,artifact_kind)
);
create index processed_reviews_text_idx on public.processed_reviews(text_id);
create index processed_reviews_config_idx on public.processed_reviews(label_config_id);
create index membership_review_idx on public.issue_membership(dataset_id,review_id);
alter table public.pipeline_datasets enable row level security;
alter table public.review_texts enable row level security;
alter table public.label_configs enable row level security;
alter table public.processed_reviews enable row level security;
alter table public.issue_membership enable row level security;
alter table public.analysis_outputs enable row level security;
-- Anonymous visitors may read explicitly published assignment data only. No public writes.
create policy published_datasets_read on public.pipeline_datasets for select to anon using(published);
create policy published_reviews_read on public.processed_reviews for select to anon using(exists(select 1 from public.pipeline_datasets d where d.id=dataset_id and d.published));
create policy published_membership_read on public.issue_membership for select to anon using(exists(select 1 from public.pipeline_datasets d where d.id=dataset_id and d.published));
create policy published_outputs_read on public.analysis_outputs for select to anon using(exists(select 1 from public.pipeline_datasets d where d.id=dataset_id and d.published));
create policy published_text_read on public.review_texts for select to anon using(exists(select 1 from public.processed_reviews r where r.text_id=review_texts.id));
create policy published_config_read on public.label_configs for select to anon using(exists(select 1 from public.processed_reviews r where r.label_config_id=label_configs.id));
grant select on public.pipeline_datasets,public.review_texts,public.label_configs,public.processed_reviews,public.issue_membership,public.analysis_outputs to anon;
commit;
