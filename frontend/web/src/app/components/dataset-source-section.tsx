import { useCallback, useEffect, useState } from 'react';
import { Database, Globe, Link2, Upload, Loader2, Eye } from 'lucide-react';
import { toast } from 'sonner';

export type DatasetMode = 'built_in' | 'openml' | 'csv_url' | 'csv_upload';

export type BuiltinDatasetMeta = {
  name: string;
  display_name: string;
  description: string;
  task_category: string;
  target: string;
};

export type DatasetPreview = {
  columns: string[];
  row_count: number;
  suggested_target: string;
  suggested_task_category: string;
  display_name: string;
  sample_rows?: Record<string, unknown>[];
};

type Props = {
  disabled?: boolean;
  mode: DatasetMode;
  onModeChange: (m: DatasetMode) => void;
  builtInName: string;
  onBuiltInNameChange: (name: string) => void;
  openmlId: string;
  onOpenmlIdChange: (v: string) => void;
  csvUrl: string;
  onCsvUrlChange: (v: string) => void;
  uploadToken: string | null;
  onUploadTokenChange: (t: string | null) => void;
  targetOverride: string;
  onTargetOverrideChange: (v: string) => void;
  /** Called whenever preview data changes (or is cleared). Parent uses stats for cost estimate. */
  onPreviewChange?: (preview: DatasetPreview | null) => void;
};

const tabs: { id: DatasetMode; label: string; icon: typeof Database }[] = [
  { id: 'built_in', label: 'Built-in', icon: Database },
  { id: 'openml', label: 'OpenML', icon: Globe },
  { id: 'csv_url', label: 'CSV URL', icon: Link2 },
  { id: 'csv_upload', label: 'Upload CSV', icon: Upload },
];

export function DatasetSourceSection({
  disabled,
  mode,
  onModeChange,
  builtInName,
  onBuiltInNameChange,
  openmlId,
  onOpenmlIdChange,
  csvUrl,
  onCsvUrlChange,
  uploadToken,
  onUploadTokenChange,
  targetOverride,
  onTargetOverrideChange,
  onPreviewChange,
}: Props) {
  const [builtIns, setBuiltIns] = useState<BuiltinDatasetMeta[]>([]);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const setPreviewAndNotify = (p: DatasetPreview | null) => {
    setPreview(p);
    onPreviewChange?.(p);
  };
  const [uploadBusy, setUploadBusy] = useState(false);

  useEffect(() => {
    fetch('/datasets/built-in', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: BuiltinDatasetMeta[]) => setBuiltIns(Array.isArray(rows) ? rows : []))
      .catch(() => setBuiltIns([]));
  }, []);

  const runPreview = useCallback(async () => {
    let source: string = mode;
    let datasetId = '';
    if (mode === 'built_in') {
      source = 'built_in';
      datasetId = builtInName;
    } else if (mode === 'openml') {
      datasetId = openmlId.trim();
    } else if (mode === 'csv_url') {
      datasetId = csvUrl.trim();
    } else {
      source = 'csv_upload';
      datasetId = uploadToken || '';
    }

    if (!datasetId) {
      toast.error('Choose or enter a dataset first');
      return;
    }

    setPreviewLoading(true);
    try {
      const res = await fetch('/datasets/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ source, dataset_id: datasetId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const d = (err as { detail?: string }).detail;
        throw new Error(typeof d === 'string' ? d : 'Preview failed');
      }
      const data = await res.json();
      setPreviewAndNotify(data as DatasetPreview);
      toast.success('Dataset loaded');
    } catch (e) {
      setPreviewAndNotify(null);
      toast.error(e instanceof Error ? e.message : 'Preview failed');
    } finally {
      setPreviewLoading(false);
    }
  }, [mode, builtInName, openmlId, csvUrl, uploadToken]);

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setUploadBusy(true);
    onUploadTokenChange(null);
    setPreviewAndNotify(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch('/datasets/csv-upload', {
        method: 'POST',
        body: fd,
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || 'Upload failed');
      }
      const { token } = await res.json();
      onUploadTokenChange(token);
      toast.success('CSV uploaded — loading preview…');
      setPreviewLoading(true);
      const pr = await fetch('/datasets/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ source: 'csv_upload', dataset_id: token }),
      });
      if (!pr.ok) {
        const err = await pr.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || 'Preview failed');
      }
      setPreviewAndNotify(await pr.json());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploadBusy(false);
      setPreviewLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-slate-300 mb-2">Dataset source</label>
        <div className="flex flex-wrap gap-2">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              disabled={disabled}
              onClick={() => onModeChange(id)}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium border transition-colors ${
                mode === id
                  ? 'bg-purple-500/20 border-purple-500/50 text-white'
                  : 'bg-slate-800/40 border-white/10 text-slate-300 hover:border-white/20'
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {mode === 'built_in' && (
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Built-in dataset</label>
          <select
            value={builtInName}
            onChange={(e) => onBuiltInNameChange(e.target.value)}
            disabled={disabled}
            className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 outline-none text-white"
          >
            {builtIns.length === 0 ? (
              <option value="weather_ri">Rhode Island Weather (default)</option>
            ) : (
              builtIns.map((d) => (
                <option key={d.name} value={d.name}>
                  {d.display_name}
                </option>
              ))
            )}
          </select>
          {builtIns.find((b) => b.name === builtInName) && (
            <p className="mt-2 text-xs text-slate-500">
              {builtIns.find((b) => b.name === builtInName)?.description}
            </p>
          )}
        </div>
      )}

      {mode === 'openml' && (
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">OpenML dataset ID</label>
            <input
              type="text"
              inputMode="numeric"
              value={openmlId}
              onChange={(e) => onOpenmlIdChange(e.target.value)}
              placeholder="e.g. 61 (Iris)"
              disabled={disabled}
              className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 outline-none text-white placeholder:text-slate-500"
            />
            <p className="mt-1 text-xs text-slate-500">Numeric ID from openml.org</p>
          </div>
        </div>
      )}

      {mode === 'csv_url' && (
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">CSV URL</label>
          <input
            type="url"
            value={csvUrl}
            onChange={(e) => onCsvUrlChange(e.target.value)}
            placeholder="https://…/data.csv"
            disabled={disabled}
            className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 outline-none text-white placeholder:text-slate-500"
          />
          <p className="mt-1 text-xs text-slate-500">Public HTTPS URL to a CSV file</p>
        </div>
      )}

      {mode === 'csv_upload' && (
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">CSV file</label>
          <label className="flex flex-col items-center justify-center w-full px-4 py-8 rounded-xl border border-dashed border-white/20 bg-slate-800/30 cursor-pointer hover:border-purple-500/40 transition-colors">
            <input type="file" accept=".csv,text/csv" className="hidden" disabled={disabled || uploadBusy} onChange={onFile} />
            {uploadBusy ? (
              <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
            ) : (
              <>
                <Upload className="w-8 h-8 text-slate-400 mb-2" />
                <span className="text-sm text-slate-300">Click to upload a .csv file</span>
                {uploadToken && (
                  <span className="mt-2 text-xs text-emerald-400 font-mono">Ready · token {uploadToken.slice(0, 8)}…</span>
                )}
              </>
            )}
          </label>
        </div>
      )}

      {(mode === 'openml' || mode === 'csv_url' || mode === 'csv_upload') && (
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Target column <span className="text-slate-500 font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={targetOverride}
            onChange={(e) => onTargetOverrideChange(e.target.value)}
            placeholder="Override auto-detected target column"
            disabled={disabled}
            className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 outline-none text-white placeholder:text-slate-500"
          />
        </div>
      )}

      {mode !== 'csv_upload' && (
        <button
          type="button"
          disabled={disabled || previewLoading}
          onClick={runPreview}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/15 border border-white/10 text-sm text-white transition-colors disabled:opacity-50"
        >
          {previewLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
          Preview dataset
        </button>
      )}

      {preview && (
        <div className="rounded-xl border border-white/10 bg-slate-950/50 p-4 space-y-2">
          <p className="text-sm font-medium text-white">{preview.display_name}</p>
          <p className="text-xs text-slate-400">
            ~{preview.row_count.toLocaleString()} rows · {preview.columns.length} columns · target:{' '}
            <code className="text-purple-300">{preview.suggested_target}</code> · {preview.suggested_task_category}
          </p>
          {preview.sample_rows && preview.sample_rows.length > 0 && (
            <div className="mt-2 overflow-x-auto text-xs">
              <table className="w-full border-collapse border border-white/10 rounded">
                <thead>
                  <tr className="bg-white/5">
                    {preview.columns.slice(0, 6).map((c) => (
                      <th key={c} className="text-left p-2 text-slate-400 font-medium border-b border-white/10">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.sample_rows.slice(0, 3).map((row, i) => (
                    <tr key={i}>
                      {preview.columns.slice(0, 6).map((c) => (
                        <td key={c} className="p-2 text-slate-300 border-b border-white/5">
                          {String((row as Record<string, unknown>)[c] ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function buildJobInputPayload(
  mode: DatasetMode,
  builtInName: string,
  openmlId: string,
  csvUrl: string,
  uploadToken: string | null,
  targetOverride: string,
): Record<string, unknown> {
  const t = targetOverride.trim();
  const target = t ? { target: t } : {};
  switch (mode) {
    case 'built_in':
      return { source: 'built_in', dataset_name: builtInName, dataset_id: '', ...target };
    case 'openml':
      return { source: 'openml', dataset_id: openmlId.trim(), ...target };
    case 'csv_url':
      return { source: 'csv_url', dataset_id: csvUrl.trim(), ...target };
    case 'csv_upload':
      return { source: 'csv_upload', dataset_id: uploadToken || '', ...target };
    default:
      return {};
  }
}
