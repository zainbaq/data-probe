-- Create test database
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'sampledb')
    CREATE DATABASE sampledb;
GO

USE sampledb;
GO

-- Read-only login for DataProbe
IF NOT EXISTS (SELECT name FROM sys.server_principals WHERE name = 'dp_readonly')
BEGIN
    CREATE LOGIN dp_readonly WITH PASSWORD = 'Readonly@1234!';
END
GO

IF NOT EXISTS (SELECT name FROM sys.database_principals WHERE name = 'dp_readonly')
BEGIN
    CREATE USER dp_readonly FOR LOGIN dp_readonly;
    EXEC sp_addrolemember 'db_datareader', 'dp_readonly';
END
GO

-- ----------------------------------------------------------------
-- Schema
-- ----------------------------------------------------------------

IF OBJECT_ID('dbo.order_items', 'U') IS NOT NULL DROP TABLE dbo.order_items;
IF OBJECT_ID('dbo.orders',      'U') IS NOT NULL DROP TABLE dbo.orders;
IF OBJECT_ID('dbo.products',    'U') IS NOT NULL DROP TABLE dbo.products;
IF OBJECT_ID('dbo.customers',   'U') IS NOT NULL DROP TABLE dbo.customers;
GO

CREATE TABLE dbo.customers (
    customer_id   INT           NOT NULL IDENTITY(1,1) PRIMARY KEY,
    first_name    NVARCHAR(100) NOT NULL,
    last_name     NVARCHAR(100) NOT NULL,
    email         NVARCHAR(255),
    phone         NVARCHAR(50),
    city          NVARCHAR(100),
    country       NVARCHAR(100),
    signup_date   DATE,
    loyalty_tier  NVARCHAR(20),
    annual_spend  DECIMAL(10,2)
);
GO

CREATE TABLE dbo.products (
    product_id  INT           NOT NULL IDENTITY(1,1) PRIMARY KEY,
    sku         NVARCHAR(50)  NOT NULL,
    name        NVARCHAR(200) NOT NULL,
    category    NVARCHAR(100),
    price       DECIMAL(10,2),
    stock_qty   INT,
    supplier_id INT,
    CONSTRAINT uq_sku UNIQUE (sku)
);
GO

CREATE TABLE dbo.orders (
    order_id      INT            NOT NULL IDENTITY(1,1) PRIMARY KEY,
    customer_id   INT,
    order_date    DATETIME,
    status        NVARCHAR(30),
    total_amount  DECIMAL(10,2),
    shipping_city NVARCHAR(100),
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES dbo.customers(customer_id)
);
GO

CREATE TABLE dbo.order_items (
    item_id    INT           NOT NULL IDENTITY(1,1) PRIMARY KEY,
    order_id   INT           NOT NULL,
    product_id INT,
    quantity   INT,
    unit_price DECIMAL(10,2),
    CONSTRAINT fk_items_order   FOREIGN KEY (order_id)   REFERENCES dbo.orders(order_id),
    CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES dbo.products(product_id)
);
GO

-- ----------------------------------------------------------------
-- Seed data
-- ----------------------------------------------------------------

INSERT INTO dbo.customers (first_name, last_name, email, phone, city, country, signup_date, loyalty_tier, annual_spend) VALUES
('Alice',  'Johnson',  'alice.johnson@email.com',  '555-0101', 'New York',    'USA',       '2021-03-15', 'Gold',   4250.00),
('Bob',    'Smith',    'bob.smith@email.com',       '555-0102', 'Los Angeles', 'USA',       '2020-07-22', 'Silver', 1800.00),
('Carol',  'Williams', 'carol.w@email.com',         NULL,       'Chicago',     'USA',       '2022-01-10', 'Bronze', 620.00),
('David',  'Brown',    NULL,                        '555-0104', 'Houston',     'USA',       '2019-11-05', 'Gold',   6100.00),
('Eva',    'Davis',    'eva.davis@email.com',       '555-0105', 'Toronto',     'Canada',    '2023-02-28', 'Silver', 2200.00),
('Frank',  'Miller',   'frank.miller@email.com',    NULL,       'London',      'UK',        '2021-08-14', 'Bronze', 430.00),
('Grace',  'Wilson',   'grace.wilson@email.com',   '555-0107', 'Sydney',      'Australia', '2020-05-03', 'Gold',   5500.00),
('Henry',  'Moore',    'henry.moore@email.com',     '555-0108', 'New York',    'USA',       '2022-09-19', 'Silver', 1100.00),
('Iris',   'Taylor',   NULL,                        NULL,       'Berlin',      'Germany',   '2023-04-01', 'Bronze', 280.00),
('James',  'Anderson', 'james.a@email.com',         '555-0110', 'Chicago',     'USA',       '2021-12-25', 'Gold',   3800.00),
('Karen',  'Thomas',   'karen.thomas@email.com',   '555-0111', 'Paris',       'France',    '2020-10-18', 'Silver', 1950.00),
('Leo',    'Jackson',  'leo.jackson@email.com',     NULL,       'New York',    'USA',       '2022-06-07', 'Bronze', 550.00),
('Maria',  'White',    'maria.white@email.com',     '555-0113', 'Miami',       'USA',       '2023-01-15', 'Gold',   4900.00),
('Nick',   'Harris',   NULL,                        '555-0114', 'Seattle',     'USA',       '2019-08-30', 'Silver', 2300.00),
('Olivia', 'Martin',   'olivia.martin@email.com',  '555-0115', 'Boston',      'USA',       '2021-05-20', 'Bronze', 390.00),
-- Intentional issues: duplicate email, missing tier, outlier spend
('Paul',   'Garcia',   'alice.johnson@email.com',  '555-0116', 'Dallas',      'USA',       '2022-03-11', NULL,     99999.00),
('Quinn',  'Martinez', 'quinn.m@email.com',         '555-0117', 'Phoenix',     'USA',       '2023-07-04', 'Bronze', 0.00),
('Rachel', 'Robinson', 'rachel.r@email.com',        '555-0118', 'Denver',      'USA',       '2020-12-01', 'Silver', 1600.00),
('Sam',    'Clark',    'sam.clark@email.com',        NULL,       'Atlanta',     'USA',       '2021-10-08', 'Gold',   3200.00),
('Tina',   'Rodriguez','tina.r@email.com',          '555-0120', 'Chicago',     'USA',       '2022-08-22', 'Bronze', 750.00);
GO

INSERT INTO dbo.products (sku, name, category, price, stock_qty, supplier_id) VALUES
('WID-001', 'Pro Widget',          'Widgets',      29.99,  500, 1),
('WID-002', 'Lite Widget',         'Widgets',      14.99, 1200, 1),
('GAD-001', 'Smart Gadget',        'Gadgets',      89.99,  200, 2),
('GAD-002', 'Mini Gadget',         'Gadgets',      49.99,  350, 2),
('ACC-001', 'Carry Case',          'Accessories',   9.99, 2000, 3),
('ACC-002', 'Power Adapter',       'Accessories',  19.99,  800, 3),
('PRE-001', 'Premium Package',     'Premium',     199.99,   50, 2),
('TOY-001', 'Fun Toy',             'Toys',         12.99,  600, 4),
('GAD-003', 'Prototype Gadget',    'Gadgets',       NULL,    0, 2),
('WID-003', 'Discontinued Widget', 'Widgets',       5.99,    0, 1);
GO

INSERT INTO dbo.orders (customer_id, order_date, status, total_amount, shipping_city) VALUES
(1,  '2024-01-05 10:22:00', 'delivered',  119.96, 'New York'),
(2,  '2024-01-07 14:10:00', 'delivered',   44.97, 'Los Angeles'),
(3,  '2024-01-09 09:05:00', 'delivered',   29.99, 'Chicago'),
(4,  '2024-01-12 16:30:00', 'delivered',  249.97, 'Houston'),
(5,  '2024-01-15 11:00:00', 'shipped',     99.98, 'Toronto'),
(6,  '2024-01-18 08:45:00', 'delivered',   24.98, 'London'),
(7,  '2024-01-20 13:20:00', 'delivered',  199.99, 'Sydney'),
(8,  '2024-02-01 10:00:00', 'processing',  59.97, 'New York'),
(10, '2024-02-03 15:40:00', 'delivered',  179.97, 'Chicago'),
(13, '2024-02-10 12:00:00', 'shipped',    219.98, 'Miami'),
(1,  '2024-02-14 09:30:00', 'cancelled',   14.99, 'New York'),
(20, '2024-02-20 17:00:00', 'delivered',   39.98, 'Chicago'),
(15, '2024-03-01 11:15:00', 'processing',  89.99, 'Boston'),
(19, '2024-03-05 14:00:00', 'delivered',  139.98, 'Atlanta'),
(4,  '2024-03-10 10:30:00', 'delivered',  399.98, 'Houston');
GO

INSERT INTO dbo.order_items (order_id, product_id, quantity, unit_price) VALUES
(1,  1, 2, 29.99), (1,  3, 1, 89.99),
(2,  2, 2, 14.99), (2,  5, 1,  9.99),
(3,  1, 1, 29.99),
(4,  7, 1,199.99), (4,  3, 1, 89.99),
(5,  4, 2, 49.99),
(6,  5, 1,  9.99), (6,  6, 1, 19.99),
(7,  7, 1,199.99),
(8,  2, 2, 14.99), (8,  5, 2,  9.99), (8, 6, 1, 19.99),
(9,  1, 3, 29.99), (9,  6, 3, 19.99),
(10, 7, 1,199.99), (10, 4, 1, 49.99),
(11, 2, 1, 14.99),
(12, 2, 2, 14.99), (12, 5, 1,  9.99),
(13, 3, 1, 89.99),
(14, 1, 2, 29.99), (14, 6, 4, 19.99),
(15, 7, 2,199.99);
GO
