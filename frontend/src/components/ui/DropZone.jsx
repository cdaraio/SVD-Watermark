import { useCallback, useRef, useState } from "react";
import { UploadCloud, ImageIcon, X } from "lucide-react";

/**
 * Drag-and-drop / click-to-browse file upload zone.
 *
 * @param {{ onFile: (f: File) => void, label: string, sublabel?: string, accept?: string }} props
 */
export default function DropZone({
  onFile,
  label = "Drop image here",
  sublabel = "PNG, JPG, BMP supported",
  accept = "image/*",
}) {
  const [preview, setPreview] = useState(null);
  const [filename, setFilename] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);
  const prevUrlRef = useRef(null);

  const handleFile = useCallback(
    (file) => {
      if (!file || !file.type.startsWith("image/")) return;
      // Revoke previous object URL to avoid memory leaks
      if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);
      const url = URL.createObjectURL(file);
      prevUrlRef.current = url;
      setPreview(url);
      setFilename(file.name);
      onFile(file);
    },
    [onFile]
  );

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    // Only clear when truly leaving (not entering child elements)
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setIsDragging(false);
    }
  }, []);

  const clear = useCallback(
    (e) => {
      e.stopPropagation();
      if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);
      prevUrlRef.current = null;
      setPreview(null);
      setFilename(null);
      if (inputRef.current) inputRef.current.value = "";
      onFile(null);
    },
    [onFile]
  );

  return (
    <div
      className={[
        "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed",
        "min-h-[200px] w-full cursor-pointer transition-all duration-200 overflow-hidden group",
        isDragging
          ? "border-cyber bg-cyber/10 scale-[1.01]"
          : preview
          ? "border-panel-border bg-panel"
          : "border-panel-border hover:border-zinc-600 bg-panel hover:bg-[#111]",
      ].join(" ")}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />

      {preview ? (
        <>
          <img
            src={preview}
            alt={filename}
            className="max-h-52 max-w-full object-contain rounded-lg p-2"
          />
          <div className="mt-2 flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#111] border border-panel-border text-xs text-zinc-400">
            <ImageIcon className="w-3 h-3" />
            <span className="max-w-[160px] truncate">{filename}</span>
          </div>
          <button
            className="absolute top-2 right-2 p-1 rounded-full bg-[#111] hover:bg-[#1a1a1a] text-zinc-500 hover:text-cyber transition-colors opacity-0 group-hover:opacity-100"
            onClick={clear}
            aria-label="Remove file"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </>
      ) : (
        <div className="flex flex-col items-center gap-3 p-8 text-center select-none">
          <div
            className={[
              "w-12 h-12 rounded-xl flex items-center justify-center transition-colors",
              isDragging ? "bg-cyber/20 text-cyber" : "bg-[#111] text-zinc-500",
            ].join(" ")}
          >
            <UploadCloud className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-zinc-300">{label}</p>
            <p className="text-xs text-zinc-500 mt-0.5">{sublabel}</p>
          </div>
          <span className="text-xs px-3 py-1 rounded-full border border-panel-border text-zinc-500 hover:border-cyber/40 hover:text-cyber transition-colors">
            Browse files
          </span>
        </div>
      )}
    </div>
  );
}
