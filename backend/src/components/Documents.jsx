import { useRef, useState } from "react";
import { api } from "../api.js";

const MAX_BYTES = 5 * 1024 * 1024;
const TYPE_LABEL = { "application/pdf": "PDF", "text/plain": "Text", "text/markdown": "Markdown" };

const formatDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

export default function Documents({ docs, setDocs }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState("");
  const [error, setError] = useState("");
  const [confirmId, setConfirmId] = useState(null);
  const [dragging, setDragging] = useState(false);

  async function upload(file) {
    if (!file || uploading) return;
    const extension = file.name.split(".").pop().toLowerCase();
    if (!["pdf", "txt", "md"].includes(extension)) {
      setError("Upload a .pdf, .txt or .md file.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setError("That file is over the 5 MB limit.");
      return;
    }
    setError("");
    setUploading(file.name);
    try {
      const created = await api.uploadDocument(file);
      setDocs((current) => [created, ...(current || [])]);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading("");
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function remove(id) {
    try {
      await api.deleteDocument(id);
      setDocs((current) => current.filter((d) => d.id !== id));
    } catch (err) {
      setError(err.message);
    } finally {
      setConfirmId(null);
    }
  }

  return (
    <section className="flex h-full min-h-0 flex-col rounded-2xl bg-white p-4 ring-1 ring-mist">
      <div className="flex items-baseline justify-between">
        <h2 className="font-display text-lg font-bold">Documents</h2>
        {docs && <span className="text-sm text-steel">{docs.length}</span>}
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          upload(e.dataTransfer.files?.[0]);
        }}
        className={`mt-3 rounded-xl border-2 border-dashed p-4 text-center ${
          dragging ? "border-navy bg-altitude" : "border-mist"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,.md"
          className="hidden"
          onChange={(e) => upload(e.target.files?.[0])}
        />
        <button
          onClick={() => inputRef.current?.click()}
          disabled={Boolean(uploading)}
          className="rounded-lg bg-navy px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy-soft disabled:opacity-60"
        >
          Upload document
        </button>
        <p className="mt-2 text-xs text-steel">PDF, TXT or Markdown, up to 5 MB. You can also drop a file here.</p>
      </div>

      {uploading && (
        <p role="status" className="mt-3 text-sm">
          Reading and indexing {uploading}…
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-alert">
          {error}
        </p>
      )}

      <ul className="mt-3 min-h-0 flex-1 divide-y divide-mist/60 overflow-y-auto">
        {docs === null && <li className="py-4 text-sm text-steel">Loading…</li>}
        {docs && docs.length === 0 && (
          <li className="py-4 text-sm text-steel">
            No documents yet. Upload one to start asking questions.
          </li>
        )}
        {docs &&
          docs.map((d) => (
            <li key={d.id} className="py-3">
              <div className="flex items-start gap-3">
                <span className="mt-0.5 rounded bg-altitude px-2 py-0.5 text-xs font-semibold">
                  {TYPE_LABEL[d.content_type] || "File"}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold" title={d.filename}>
                    {d.filename}
                  </p>
                  <p className="text-xs text-steel">{formatDate(d.created_at)}</p>
                </div>
              </div>
              <div className="mt-2 text-right text-xs">
                {confirmId === d.id ? (
                  <span className="space-x-3">
                    <button onClick={() => remove(d.id)} className="font-semibold text-alert underline">
                      Yes, remove
                    </button>
                    <button onClick={() => setConfirmId(null)} className="font-semibold text-steel underline">
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button onClick={() => setConfirmId(d.id)} className="font-semibold text-steel underline">
                    Remove
                  </button>
                )}
              </div>
            </li>
          ))}
      </ul>
    </section>
  );
}