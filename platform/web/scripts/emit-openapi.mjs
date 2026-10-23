/**
 * Generate OpenAPI from the Zod contracts.
 *
 * The schemas are the single source of truth: they validate real requests AND
 * produce this document. Hand-writing the spec alongside the validation is how
 * a contract doc ends up describing an API that no longer exists.
 *
 *   npm run contracts   ->  ../../docs/openapi/{cms,pas,dms}.json
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { zodToJsonSchema } from "zod-to-json-schema";

import * as cms from "../src/lib/contracts/cms.js";
import * as pas from "../src/lib/contracts/pas.js";
import * as dms from "../src/lib/contracts/dms.js";
import { ApiError, IDEMPOTENCY_RULE } from "../src/lib/contracts/common.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, "../../../docs/openapi");

const SYSTEMS = {
  cms: {
    title: "ClaimSense ⇄ Claims Management System",
    description:
      "The claim, the first notice of loss, the notes, the fraud signals and "
      + "the decision. The ONLY system ClaimSense writes to, and only after a "
      + "licensed adjuster confirms.\n\n" + IDEMPOTENCY_RULE,
    schemas: cms,
    paths: {
      "/claims": { get: "List the claim queue, scoped to the calling seat." },
      "/claims/{id}": { get: "One claim." },
      "/claims/{id}/fnol": { get: "First notice of loss. Attacker-influenceable text." },
      "/claims/{id}/notes": { get: "Adjuster notes." },
      "/claims/{id}/fraud-signals": { get: "Recorded fraud indicators with their weights." },
      "/claims/{id}/decisions": {
        get: "Decision history.",
        post: "WRITE — record a recommendation. Idempotency-Key required.",
      },
      "/decisions/{id}/confirm": {
        post: "WRITE — a LICENSED adjuster confirms or overrides. "
            + "Idempotency-Key required. Refused without a licence.",
      },
      "/adjusters/{id}": { get: "One adjuster seat." },
    },
  },
  pas: {
    title: "ClaimSense ⇄ Policy Administration System",
    description:
      "Cover, limits, deductibles and the policy clause corpus. READ-ONLY. "
      + "There is no write contract, deliberately: a claims co-pilot that could "
      + "alter a policy could manufacture the coverage it then finds.",
    schemas: pas,
    paths: {
      "/policies/{id}": {
        get: "One policy. 404 is a CONTRACTUAL outcome — the claim/policy "
           + "reference crosses a vendor boundary with no foreign key, so a "
           + "dangling id is reachable and must be reported, never a 500.",
      },
      "/policies/{id}/coverages": { get: "Limits, deductibles and coinsurance." },
      "/clauses": { get: "The policy clause corpus retrieval ranks over." },
    },
  },
  dms: {
    title: "ClaimSense ⇄ Document Store",
    description:
      "Documents and the text OCR pulled out of them.\n\nPoisoned documents are "
      + "returned FLAGGED, not filtered. If this API dropped them the agent "
      + "could never record that it refused one, and a quarantine nobody can "
      + "see is a quarantine nobody can audit.\n\n" + IDEMPOTENCY_RULE,
    schemas: dms,
    paths: {
      "/documents": { get: "Documents for a claim, including any flagged poisoned." },
      "/document-requests": {
        post: "WRITE — ask the claimant for a missing document. "
            + "Idempotency-Key required: a retry must not send two letters.",
      },
    },
  },
};

mkdirSync(OUT, { recursive: true });

for (const [key, sys] of Object.entries(SYSTEMS)) {
  const components = { schemas: { ApiError: strip(zodToJsonSchema(ApiError, "ApiError")) } };
  for (const [name, schema] of Object.entries(sys.schemas)) {
    if (schema?._def) components.schemas[name] = strip(zodToJsonSchema(schema, name));
  }

  const paths = {};
  for (const [p, ops] of Object.entries(sys.paths)) {
    paths[p] = {};
    for (const [method, summary] of Object.entries(ops)) {
      const op = {
        summary,
        security: [{ bearerAuth: [] }],
        responses: {
          200: { description: "OK" },
          401: { description: "No or unrecognised key",
                 content: { "application/json": { schema: ref("ApiError") } } },
          403: { description: "Key is valid but scoped to another system, or "
                            + "the seat may not access this resource",
                 content: { "application/json": { schema: ref("ApiError") } } },
          422: { description: "Body failed contract validation",
                 content: { "application/json": { schema: ref("ApiError") } } },
        },
      };
      if (method === "post") {
        op.parameters = [{
          name: "Idempotency-Key", in: "header", required: true,
          schema: { type: "string" },
          description: "Unique per (adjuster, system). A replay returns the "
                     + "original record; reuse with a different body is 409.",
        }];
        op.responses[201] = { description: "Created" };
        op.responses[409] = { description: "Idempotency-Key reused with a different body",
                              content: { "application/json": { schema: ref("ApiError") } } };
      }
      paths[p][method] = op;
    }
  }

  const doc = {
    openapi: "3.0.3",
    info: { title: sys.title, version: "1.0.0", description: sys.description },
    servers: [{ url: `http://localhost:3200/api/${key}/v1` }],
    components: {
      ...components,
      securitySchemes: {
        bearerAuth: { type: "http", scheme: "bearer",
          description: `Scoped to the ${key.toUpperCase()} contract. A key for `
                     + `another system is refused with 403 wrong_system.` },
      },
    },
    paths,
  };
  const file = resolve(OUT, `${key}.json`);
  writeFileSync(file, JSON.stringify(doc, null, 2) + "\n");
  console.log(`  ${key}.json  ${Object.keys(paths).length} paths, `
            + `${Object.keys(components.schemas).length} schemas`);
}

function ref(name) { return { $ref: `#/components/schemas/${name}` }; }
// zodToJsonSchema wraps output in {$ref, definitions}; OpenAPI wants the bare
// schema under components.schemas, so the wrapper is unpicked here.
function strip(generated) {
  const defs = generated.definitions ?? {};
  const only = Object.values(defs)[0];
  return only ?? generated;
}
