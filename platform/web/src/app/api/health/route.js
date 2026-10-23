import { ok } from "@/lib/api/respond";
import { queryOne } from "@/lib/db";

// Unauthenticated on purpose: a health check that needs a credential cannot be
// used by the thing that starts before credentials exist (docker-compose).
export async function GET() {
  try {
    const row = await queryOne("SELECT count(*)::int AS claims FROM cms.claims");
    return ok({ status: "ok", database: "up", claims: row?.claims ?? 0 });
  } catch (err) {
    return ok({ status: "degraded", database: "down", error: err.message },
              { status: 503 });
  }
}
