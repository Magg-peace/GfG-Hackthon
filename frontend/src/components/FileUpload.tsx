

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
      <div className="flex items-center gap-2.5 px-3.5 py-2.5 bg-[#34d399]/5 border border-[#34d399]/12 rounded-xl">
        <div className="w-6 h-6 rounded-lg bg-[#34d399]/10 flex items-center justify-center flex-shrink-0">
          <CheckCircle className="w-3.5 h-3.5 text-[#34d399]" />
        </div>
        <FileSpreadsheet className="w-3.5 h-3.5 text-[#34d399]/70 flex-shrink-0" />
        <span className="text-[11px] text-[#34d399] truncate font-medium">{currentFile}</span>
        <button
          onClick={onClearSession}
          className="ml-auto flex-shrink-0 text-[#5a6380] hover:text-white transition-colors p-0.5 rounded hover:bg-[#151b30]"
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
        className={`border border-dashed rounded-xl px-3 py-3.5 text-center cursor-pointer transition-all duration-300 ${
          isDragActive
            ? "border-[#4f8fff]/50 bg-[#4f8fff]/5 shadow-[0_0_30px_rgba(79,143,255,0.08)]"
            : "border-[#1c2340] hover:border-[#2a3355] bg-[#0c1021] hover:bg-[#0e1225]"
        } ${isUploading ? "pointer-events-none opacity-50" : ""}`}
      >
        <input {...getInputProps()} />
        {isUploading ? (
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="w-5 h-5 text-[#4f8fff] animate-spin" />
            <p className="text-[11px] text-[#5a6380]">Uploading & processing...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-[#151b30] flex items-center justify-center">
              <Upload className="w-4 h-4 text-[#5a6380]" />
            </div>
            <p className="text-[11px] text-[#8b95b0]">
              {isDragActive
                ? "Drop your CSV here"
                : "Upload CSV to analyze your own data"}
            </p>
            <p className="text-[9px] text-[#3a4460]">Max 50MB</p>
          </div>
        )}
      </div>
      {error && (
        <p className="text-[11px] text-[#f87171] mt-2">{error}</p>
      )}
    </div>
  );
}
