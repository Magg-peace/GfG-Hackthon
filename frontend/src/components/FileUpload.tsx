

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
      <div className="flex items-center gap-2.5 px-3.5 py-2.5 bg-[#ECFDF5] border border-[#BBF7D0] rounded-xl">
        <div className="w-6 h-6 rounded-lg bg-[#BBF7D0]/50 flex items-center justify-center flex-shrink-0">
          <CheckCircle className="w-3.5 h-3.5 text-[#059669]" />
        </div>
        <FileSpreadsheet className="w-3.5 h-3.5 text-[#059669]/70 flex-shrink-0" />
        <span className="text-[11px] text-[#059669] truncate font-medium">{currentFile}</span>
        <button
          onClick={onClearSession}
          className="ml-auto flex-shrink-0 text-[#9CA3AF] hover:text-[#1F2937] transition-colors p-0.5 rounded hover:bg-[#F1F5F9]"
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
            ? "border-[#A5B4FC]/60 bg-[#EEF2FF] shadow-[0_0_30px_rgba(165,180,252,0.12)]"
            : "border-[#E5E7EB] hover:border-[#C7D2FE] bg-[#F8FAFC] hover:bg-[#F1F5F9]"
        } ${isUploading ? "pointer-events-none opacity-50" : ""}`}
      >
        <input {...getInputProps()} />
        {isUploading ? (
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="w-5 h-5 text-[#818CF8] animate-spin" />
            <p className="text-[11px] text-[#9CA3AF]">Uploading & processing...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-[#EEF2FF] flex items-center justify-center">
              <Upload className="w-4 h-4 text-[#818CF8]" />
            </div>
            <p className="text-[11px] text-[#6B7280]">
              {isDragActive
                ? "Drop your CSV here"
                : "Upload CSV to analyze your own data"}
            </p>
            <p className="text-[9px] text-[#9CA3AF]">Max 50MB</p>
          </div>
        )}
      </div>
      {error && (
        <p className="text-[11px] text-[#EF4444] mt-2">{error}</p>
      )}
    </div>
  );
}
