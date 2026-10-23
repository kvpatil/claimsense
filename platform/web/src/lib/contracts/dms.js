import { z } from "zod";
import { DocType, IsoDateTime } from "./common.js";

/** DMS — Document Store. */

export const Document = z.object({
  document_id: z.number().int(),
  claim_id: z.number().int(),
  doc_type: DocType,
  filename: z.string(),
  uploaded_at: IsoDateTime,
  page_count: z.number().int().positive(),
  extracted_text: z.string(),
  // Flagged, NOT filtered server-side. The quarantine must happen where it can
  // be recorded: if this endpoint silently dropped poisoned documents the
  // agent could never report that it refused one, and an invisible control is
  // an unauditable one.
  is_poisoned: z.boolean(),
});

export const ListDocumentsResponse = z.object({
  claim_id: z.number().int(),
  documents: z.array(Document),
  count: z.number().int(),
});

/** The one DMS write: asking the claimant for a document that is missing.
 *
 * This is what a MORE_INFO outcome produces. Idempotent, because asking twice
 * because a pipeline retried must not send the claimant two letters.
 */
export const CreateDocumentRequest = z.object({
  claim_id: z.number().int(),
  doc_type: DocType,
  // Required and non-trivial: the claimant is told WHY, and "additional
  // documentation required" is not a reason a person can act on.
  reason: z.string().min(10).max(500),
});

export const DocumentRequest = z.object({
  request_id: z.number().int(),
  claim_id: z.number().int(),
  doc_type: DocType,
  reason: z.string(),
  requested_by: z.number().int(),
  requested_at: IsoDateTime,
  fulfilled_at: IsoDateTime.nullable(),
});

export const CreateDocumentRequestResponse = z.object({
  request: DocumentRequest,
  idempotent_replay: z.boolean().optional(),
});
