-- Create a CDC source table in the OLTP PostgreSQL (inventory DB)
CREATE TABLE IF NOT EXISTS public.customers (
  id SERIAL PRIMARY KEY,
  name TEXT,
  email TEXT
);

-- Ensure UPDATE/DELETE have full "before" data (useful for downstream)
ALTER TABLE public.customers REPLICA IDENTITY FULL;

-- Seed a few rows (safe to run multiple times)
INSERT INTO public.customers(name, email)
VALUES ('Alice', 'alice@example.com')
ON CONFLICT DO NOTHING;

INSERT INTO public.customers(name, email)
VALUES ('Bob', 'bob@example.com')
ON CONFLICT DO NOTHING;
