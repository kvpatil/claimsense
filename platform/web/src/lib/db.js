import pg from "pg";
const { Pool, types } = pg;

/* BIGINT (oid 20) arrives as a STRING by default.
 *
 * node-postgres does that because an int8 can exceed JS's safe integer range
 * and it will not silently lose precision for you. Here it was actively
 * harmful: claimed_amount_cents came back as "2900000", which fails the
 * z.number().int() contract and — worse — makes `a + b` string concatenation
 * in any arithmetic that slips past validation.
 *
 * Parsing as Number is safe for THIS schema and it is worth saying why rather
 * than just doing it. Number.MAX_SAFE_INTEGER is 2^53-1, which in cents is
 * about $90 trillion; claim ids, limits and settlements are nowhere near it.
 * If a column ever could exceed that, it must not use this parser.
 */
types.setTypeParser(types.builtins.INT8, (v) => {
  const n = Number(v);
  if (!Number.isSafeInteger(n)) {
    throw new Error(`int8 ${v} exceeds JS safe integer range — this column `
                  + `cannot be parsed as a Number`);
  }
  return n;
});

/* NUMERIC (oid 1700) is arbitrary-precision and also arrives as a string.
 * Only `confidence` uses it, which is a 0-1 ratio and never money. */
types.setTypeParser(types.builtins.NUMERIC, (v) => (v === null ? null : Number(v)));

/** One pool per process.
 *
 * Next dev reloads modules on every edit, and a fresh Pool per reload leaks
 * connections until Postgres refuses new ones — which presents as the app
 * "randomly" dying after twenty saves. Stashing it on globalThis is the
 * standard fix and is why this is not simply `new Pool()`.
 */
const globalForPg = globalThis;

export const pool =
  globalForPg.__claimsensePool ??
  new Pool({
    connectionString:
      process.env.CLAIMSENSE_DB_URL ??
      "postgresql://claimsense:claimsense@localhost:5433/claimsense",
    max: 10,
    idleTimeoutMillis: 30_000,
  });

if (process.env.NODE_ENV !== "production") globalForPg.__claimsensePool = pool;

export async function query(text, params = []) {
  const res = await pool.query(text, params);
  return res.rows;
}

export async function queryOne(text, params = []) {
  const rows = await query(text, params);
  return rows[0] ?? null;
}
