import { ok, apiError, requireAuth } from "@/lib/api/respond";
import { queryOne } from "@/lib/db";

export async function GET(req, { params }) {
  const auth = await requireAuth(req, "cms", "get_adjuster");
  if (!auth.ok) return auth.response;

  const adjuster = await queryOne(
    `SELECT adjuster_id::int, full_name, email, license_number, role, scope, active
       FROM cms.adjusters WHERE adjuster_id = $1`,
    [params.id]
  );
  if (!adjuster) return apiError(404, "not_found", `Adjuster ${params.id} not found.`);
  return ok({ adjuster });
}
