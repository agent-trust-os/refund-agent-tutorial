-- Refund Bot schema. Every table is scoped by run_id: a run seeds its own rows, so runs never see
-- each other's data and a run's history stays in the database after it ends.
-- Applied by the Postgres container the first time its volume is created (docker compose down -v resets it).

CREATE TABLE IF NOT EXISTS customers (
    run_id      text NOT NULL,
    customer_id text NOT NULL,
    name        text NOT NULL,
    email       text NOT NULL,
    ssn         text NOT NULL,
    card_number text NOT NULL,
    PRIMARY KEY (run_id, customer_id)
);

CREATE TABLE IF NOT EXISTS orders (
    run_id         text NOT NULL,
    order_id       text NOT NULL,
    customer_id    text NOT NULL,
    total          numeric(12, 2) NOT NULL,
    currency       text NOT NULL,
    status         text NOT NULL,
    delivered_late boolean NOT NULL,
    PRIMARY KEY (run_id, order_id)
);

CREATE TABLE IF NOT EXISTS tickets (
    run_id      text NOT NULL,
    ticket_id   text NOT NULL,
    customer_id text NOT NULL,
    order_id    text,
    body        text NOT NULL,
    status      text NOT NULL DEFAULT 'open',      -- open, resolved or escalated
    note        text NOT NULL DEFAULT '',
    PRIMARY KEY (run_id, ticket_id)
);

-- UNIQUE (run_id, order_id, amount) is the idempotency key: the same refund twice in one run is stored once.
CREATE TABLE IF NOT EXISTS refunds (
    run_id     text NOT NULL,
    refund_id  text NOT NULL,
    order_id   text NOT NULL,
    amount     numeric(12, 2) NOT NULL,
    currency   text NOT NULL,
    reason     text NOT NULL,
    status     text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, refund_id),
    UNIQUE (run_id, order_id, amount)
);

-- The ground truth of what really ran, written before each tool acts.
CREATE TABLE IF NOT EXISTS actions (
    run_id     text NOT NULL,
    seq        integer NOT NULL,
    tool       text NOT NULL,
    args       json NOT NULL,   -- json, not jsonb: keeps the keys in the order the tool received them
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, seq)
);
