"use client";

import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileSpreadsheet, CheckCircle, Loader2, X } from "lucide-react";
import { uploadCsv, UploadResponse } from "@/lib/api";

interface FileUploadProps {
  onUploadComplete: (result: UploadResponse) => void;
  currentFile?: string | null;
  onClearSession: () => void;
}

export default function FileUpload({
  onUploadComplete,
  currentFile,
  onClearSession,
}: FileUploadProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      setIsUploading(true);
      setError(null);

      try {
        const result = await uploadCsv(file);
        onUploadComplete(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setIsUploading(false);
      }
    },
    [onUploadComplete]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"] },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024,
    disabled: isUploading,
  });

  if (currentFile) {
    return (
      <div className="flex items-center gap-2 px-3 py-2.5 bg-emerald-900/20 border border-emerald-700/40 rounded-xl">
        <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
        <FileSpreadsheet className="w-4 h-4 text-emerald-400 flex-shrink-0" />
        <span className="text-xs text-emerald-300 truncate">{currentFile}</span>
        <button
          onClick={onClearSession}
          className="ml-auto flex-shrink-0 text-slate-500 hover:text-slate-300 transition-colors"
          title="Switch to default dataset"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div>
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl px-4 py-4 text-center cursor-pointer transition-all ${
          isDragActive
            ? "border-blue-500 bg-blue-600/10"
            : "border-slate-700 hover:border-slate-600 bg-slate-900/50"
        } ${isUploading ? "pointer-events-none opacity-60" : ""}`}
      >
        <input {...getInputProps()} />
        {isUploading ? (
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="w-6 h-6 text-brand-400 animate-spin" />
            <p className="text-xs text-slate-400">Uploading & processing...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload className="w-6 h-6 text-slate-500" />
            <p className="text-xs text-slate-400">
              {isDragActive
                ? "Drop your CSV here"
                : "Upload CSV to analyze your own data"}
            </p>
            <p className="text-[10px] text-slate-600">Max 50MB</p>
          </div>
        )}
      </div>
      {error && (
        <p className="text-xs text-red-400 mt-2">{error}</p>
      )}
    </div>
  );
}
