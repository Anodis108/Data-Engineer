-- Database: inventory (cdc-postgres)
-- User: dbz / pass: dbz

-- Bạn có thể đổi table cho đúng với cdc_bootstrap.sql của bạn.
-- Ở đây giả sử có bảng public.customers (giống bài classic Debezium).
-- Nếu bạn seed bảng khác, sửa lại tên bảng và cột cho khớp.

-- insert
INSERT INTO public.customers(name, email)
VALUES
  ('Alice', 'alice@example.com'),
  ('Bob', 'bob@example.com');

-- update
UPDATE public.customers
SET email = 'alice+updated@example.com'
WHERE name = 'Alice';

-- delete
DELETE FROM public.customers
WHERE name = 'Bob';