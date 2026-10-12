-- Applied after the initial schema: dashboard artifacts are public only when published.
-- The complete processed/source tables stay private, including after dashboard publication.
begin;
drop policy if exists published_reviews_read on public.processed_reviews;
drop policy if exists published_membership_read on public.issue_membership;
drop policy if exists published_text_read on public.review_texts;
drop policy if exists published_config_read on public.label_configs;
revoke select on public.review_texts,public.label_configs,public.processed_reviews,public.issue_membership from anon;
commit;
