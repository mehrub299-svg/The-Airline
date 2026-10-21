import { useRef, useState } from "react";
import { ACCEPTED_EXTENSIONS, MAX_UPLOAD_BYTES, api } from "../api.js";

const MAX_BATCH = 20;

const extensionOf = (name) => (name.includes(".") ? name.split(".").pop().toLowerCase() : "");

const formatDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

export default function DocumentsPanel({ docs, setDocs, unselected, setUnselected, onClose }) {
  const inputRef = useRef(null);
  const [progress, setProgress] = useState(null);
  const [errors, setErrors] = useState([]);
  const [removeError, setRemoveError] = useState("");
  const [confirmId, setConfirmId] = useState(null);
  const [dragging, setDragging] = useState(false);

  const list = docs || [];
  const selectedCount = list.filter((d) => !unselected.has(d.id)).length;
  const uploading = progress !== null;

  async function uploadFiles(fileList) {
    const files = Array.from(fileList || []);
    if (files.length === 0 || uploading) return;

    setErrors([]);
    setRemoveError("");
    const problems = [];
    const batch = files.slice(0, MAX_BATCH);
    if (files.length > MAX_BATCH) {
      problems.push({
        name: `${files.length - MAX_BATCH} more files`,
        message: `Only ${MAX_BATCH} files can be uploaded at once.`,
      });
    }

    for (let i = 0; i < batch.length; i++) {
      const file = batch[i];
      if (!ACCEPTED_EXTENSIONS.includes(`.${extensionOf(file.name)}`)) {
        problems.push({ name: file.name, message: "This file type is not supported." });
        continue;
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        problems.push({ name: file.name, message: "Over the 5 MB limit." });
        continue;
      }
      setProgress({ index: i + 1, total: batch.length, name: file.name });
      try {
        const created = await api.uploadDocument(file);
        setDocs((current) => [created, ...(current || [])]);
      } catch (err) {
        problems.push({ name: file.name, message: err.message });
      }
    }

    setProgress(null);
    setErrors(problems);
    if (inputRef.current) inputRef.current.value = "";
  }

  async function remove(id) {
    setRemoveError("");
    try {
      await api.deleteDocument(id);
      setDocs((current) => current.filter((d) => d.id !== id));
    } catch (err) {
      setRemoveError(err.message);
    } finally {
      setConfirmId(null);
    }
  }

  function toggle(id) {
    setUnselected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const selectAll = () => setUnselected(new Set());
  const selectNone = () => setUnselected(new Set(list.map((d) => d.id)));

  return (
    <section className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between px-4 pt-4">
        <h2 className="font-display text-lg font-bold">Documents</h2>
        <button onClick={onClose} className="text-sm font-semibold text-muted underline md:hidden">
          Close
        </button>
      </div>

      <p className="px-4 pt-1 text-sm text-muted">
        {docs === null
          ? "Loading…"
          : list.length === 0
          ? "No documents yet."
          : `Answering from ${selectedCount} of ${list.length}`}
      </p>

      {list.length > 1 && (
        <div className="flex gap-4 px-4 pt-2 text-xs font-semibold">
          <button onClick={selectAll} className="underline">
            Select all
          </button>
          <button onClick={selectNone} className="underline">
            Select none
          </button>
        </div>
      )}

      <ul className="mt-2 min-h-0 flex-1 divide-y divide-line overflow-y-auto px-4">
        {docs && list.length === 0 && (
          <li className="py-4 text-sm text-muted">Upload a document to start asking questions.</li>
        )}
        {list.map((d) => (
          <li key={d.id} className="py-3">
            <div className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={!unselected.has(d.id)}
                onChange={() => toggle(d.id)}
                aria-label={`Use ${d.filename}`}
                className="mt-1 h-4 w-4 shrink-0"
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold" title={d.filename}>
                  {d.filename}
                </p>
                <p className="mt-0.5 text-xs text-muted">
                  <span className="mr-2 rounded bg-page px-1.5 py-0.5 font-semibold">
                    {extensionOf(d.filename).toUpperCase() || "FILE"}
                  </span>
                  {formatDate(d.created_at)}
                </p>
              </div>
            </div>
            <div className="mt-1 text-right text-xs">
              {confirmId === d.id ? (
                <span className="space-x-3">
                  <button onClick={() => remove(d.id)} className="font-semibold text-alert underline">
                    Yes, remove
                  </button>
                  <button onClick={() => setConfirmId(null)} className="font-semibold text-muted underline">
                    Cancel
                  </button>
                </span>
              ) : (
                <button onClick={() => setConfirmId(d.id)} className="font-semibold text-muted underline">
                  Remove
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>

      <div className="border-t border-line p-4">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            uploadFiles(e.dataTransfer.files);
          }}
          className={`rounded-xl border-2 border-dashed p-4 text-center ${
            dragging ? "border-brand bg-page" : "border-line"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPTED_EXTENSIONS.join(",")}
            className="hidden"
            onChange={(e) => uploadFiles(e.target.files)}
          />
          <button
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-onbrand hover:bg-brand-hover disabled:opacity-60"
          >
            Upload documents
          </button>
          <p className="mt-2 text-xs text-muted">
            PDF, Word, text and code files, up to 5 MB each. Select or drop several at once, up to {MAX_BATCH}.
          </p>
        </div>

        {progress && (
          <p role="status" className="mt-3 text-sm">
            Reading and indexing {progress.index} of {progress.total}: {progress.name}…
          </p>
        )}
        {errors.length > 0 && (
          <ul role="alert" className="mt-3 space-y-1 text-sm text-alert">
            {errors.map((e, i) => (
              <li key={i}>
                <span className="font-semibold">{e.name}:</span> {e.message}
              </li>
            ))}
          </ul>
        )}
        {removeError && (
          <p role="alert" className="mt-3 text-sm text-alert">
            {removeError}
          </p>
        )}
      </div>
    </section>
  );
}