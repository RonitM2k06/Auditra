import { useState } from 'react';
import { ImageUp } from 'lucide-react';
import { Button, CONTENT_TYPES, cx, Field, inputCls, Page, PageHeader, useToast } from '../components/ui';
import type { Brand } from '../types';
import { api } from '../api';

const MAX_MB = 4;

export function NewCreative({ brand, canCreate, navigate }: { brand: Brand; canCreate: boolean; navigate: (p: string, id?: string | null) => void }) {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [type, setType] = useState('social_post');
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pick = (f: File | undefined) => {
    setError(null);
    if (!f) return;
    if (f.size > MAX_MB * 1024 * 1024) return setError(`That file is ${(f.size / 1024 / 1024).toFixed(1)} MB; the limit is ${MAX_MB} MB.`);
    setFile(f);
    setPreview(URL.createObjectURL(f));
    if (!title) setTitle(f.name.replace(/\.[a-z]+$/i, '').replace(/[-_]+/g, ' '));
  };

  const submit = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const item = await api.uploadCreative(brand.id, title.trim() || 'Untitled creative', type, file);
      await api.runReview(item.id, {});
      toast(`Extracted ${item.image?.ocr.lines.length ?? 0} text lines and analysed the creative.`, 'success');
      navigate('studio', item.id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page width="max-w-3xl">
      <PageHeader
        title="Review a creative"
        description="Upload a PNG or JPEG ad, banner or social tile. AUDITRA reads its text with on-server OCR, applies the same brand rules and claim checks as copy, and measures contrast, palette and logo similarity."
      />
      {!canCreate ? (
        <p className="rounded-md border border-line bg-white px-4 py-3 text-[13px] text-ink-600">Reviewers can analyse existing creatives but not upload new ones. Sign in as a creator or admin to upload.</p>
      ) : (
        <div className="space-y-4">
          <label
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
            className={cx('flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed bg-white px-6 py-10 text-center transition-colors', drag ? 'border-pine-500 bg-pine-50/40' : 'border-ink-300 hover:border-ink-400')}
          >
            <input type="file" accept="image/png,image/jpeg" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} />
            {preview ? <img src={preview} alt="Selected creative" className="max-h-72 rounded-md shadow-sm" /> : <ImageUp className="h-8 w-8 text-ink-400" strokeWidth={1.5} />}
            <p className="mt-3 text-[14px] font-medium text-ink-900">{file ? file.name : 'Drop an image here or choose a file'}</p>
            <p className="mt-1 text-[12.5px] text-ink-500">PNG or JPEG, up to {MAX_MB} MB, 64–6000 px per side. Files are checked by content, not by name.</p>
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Title"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
            <Field label="Channel">
              <select className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
                {Object.entries(CONTENT_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Field>
          </div>
          {error && <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-800">{error}</p>}
          <div className="flex items-center gap-3">
            <Button variant="primary" onClick={submit} disabled={!file || busy}>{busy ? 'Reading text and analysing…' : 'Upload and analyse'}</Button>
            <p className="text-[12.5px] text-ink-500">
              No file to hand? Sample creatives are in the repo under <code className="rounded bg-ink-100 px-1">samples/creatives/</code>, and three are already in this workspace.
            </p>
          </div>
          <p className="text-[12px] leading-relaxed text-ink-500">
            The image is stored with its version so reviewers see exactly what was analysed and approved. It is never sent to an external service.
          </p>
        </div>
      )}
    </Page>
  );
}
