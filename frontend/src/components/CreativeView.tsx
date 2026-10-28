import { useState } from 'react';
import { CATEGORY_LABEL, cx, SEV_META } from './ui';
import type { CreativeImage, Finding } from '../types';

const SEV_STROKE: Record<string, string> = { critical: '#DC2626', high: '#F59E0B', medium: '#FB923C', low: '#0EA5E9' };

export function regionsOf(f: Finding): number[][] {
  if (!f.region_json) return [];
  try {
    return (JSON.parse(f.region_json) as Array<{ box?: number[] }>).map((r) => r.box ?? []).filter((b) => b.length === 4);
  } catch {
    return [];
  }
}

interface Props {
  image: CreativeImage;
  findings: Finding[];
  selected: string | null;
  onSelect: (id: string) => void;
}

/** The uploaded creative with OCR text boxes and finding regions drawn in image coordinates. */
export function CreativeView({ image, findings, selected, onSelect }: Props) {
  const [showOcr, setShowOcr] = useState(true);
  const [tab, setTab] = useState<'ocr' | 'visual'>('ocr');
  const open = findings.filter((f) => !f.is_applied && !f.is_dismissed);
  const { ocr, visual } = image;
  const stroke = Math.max(2, image.width / 300);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3 text-[12.5px] text-ink-600">
        <span className="rounded bg-ink-100 px-1.5 py-0.5 font-mono text-[11.5px]">{image.width}×{image.height} · {(image.byte_size / 1024).toFixed(0)} KB · {image.mime_type.replace('image/', '').toUpperCase()}</span>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={showOcr} onChange={(e) => setShowOcr(e.target.checked)} className="accent-pine-600" />
          OCR text boxes
        </label>
        <span className="ml-auto flex items-center gap-2">
          {(['critical', 'high', 'medium', 'low'] as const).map((s) => (
            <span key={s} className="flex items-center gap-1"><span className="h-2 w-3 rounded-sm" style={{ background: SEV_STROKE[s] }} />{SEV_META[s].label}</span>
          ))}
        </span>
      </div>

      <figure className="relative overflow-hidden rounded-lg border border-line bg-white shadow-sm">
        <img src={image.url} alt="Uploaded creative" className="block h-auto w-full" />
        <svg viewBox={`0 0 ${image.width} ${image.height}`} className="absolute inset-0 h-full w-full" aria-hidden>
          {showOcr && ocr.lines.map((ln, i) => {
            const [x0, y0, x1, y1] = ln.box;
            return <rect key={`o${i}`} x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="none" stroke="#64748B" strokeDasharray={`${stroke * 3} ${stroke * 2}`} strokeWidth={stroke * 0.7} opacity={0.7} />;
          })}
          {open.flatMap((f) =>
            regionsOf(f).map((b, i) => (
              <rect
                key={`${f.id}-${i}`}
                x={b[0] - stroke * 2}
                y={b[1] - stroke * 2}
                width={b[2] - b[0] + stroke * 4}
                height={b[3] - b[1] + stroke * 4}
                rx={stroke * 2}
                fill={SEV_STROKE[f.severity]}
                fillOpacity={selected === f.id ? 0.22 : 0.08}
                stroke={SEV_STROKE[f.severity]}
                strokeWidth={selected === f.id ? stroke * 2.2 : stroke * 1.4}
                className="cursor-pointer"
                style={{ pointerEvents: 'all' }}
                onClick={() => onSelect(f.id)}
              >
                <title>{CATEGORY_LABEL[f.category] ?? f.category}: {f.matched_text}</title>
              </rect>
            )),
          )}
        </svg>
      </figure>

      <div className="rounded-lg border border-line bg-white">
        <div className="flex border-b border-line text-[13px]">
          {(['ocr', 'visual'] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} className={cx('px-4 py-2 font-medium', tab === t ? 'border-b-2 border-pine-600 text-ink-900' : 'text-ink-500 hover:text-ink-800')}>
              {t === 'ocr' ? `Extracted text (${ocr.lines.length} lines)` : 'Visual checks'}
            </button>
          ))}
        </div>
        {tab === 'ocr' ? (
          <div className="p-4">
            <p className="mb-3 text-[12.5px] leading-relaxed text-ink-500">
              Read by {ocr.engine} on the server. OCR can misread stylised or small text; rule results apply to this transcription, not to the pixels.
              Lines under 80% confidence are flagged for human checking.
            </p>
            {ocr.lines.length === 0 ? (
              <p className="text-[13px] italic text-ink-500">No readable text was found in this image.</p>
            ) : (
              <table className="w-full text-left text-[13px]">
                <thead className="text-[11px] uppercase tracking-wider text-ink-400">
                  <tr><th className="pb-1.5 font-medium">#</th><th className="pb-1.5 font-medium">Text</th><th className="pb-1.5 text-right font-medium">Confidence</th></tr>
                </thead>
                <tbody>
                  {ocr.lines.map((ln, i) => (
                    <tr key={i} className="border-t border-line/70">
                      <td className="py-1.5 pr-2 tabular-nums text-ink-400">{i + 1}</td>
                      <td className="py-1.5 font-mono text-[12.5px] text-ink-800">{ln.text}</td>
                      <td className={cx('py-1.5 text-right tabular-nums', ln.confidence < 0.8 ? 'font-medium text-amber-700' : 'text-ink-600')}>{Math.round(ln.confidence * 100)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : (
          <div className="space-y-5 p-4 text-[13px]">
            {!visual.contrast ? (
              <p className="italic text-ink-500">Run the analysis to compute visual checks.</p>
            ) : (
              <>
                <section>
                  <h4 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-400">Text contrast (WCAG 2.2 AA)</h4>
                  <ul className="mt-2 space-y-1.5">
                    {visual.contrast.map((c) => (
                      <li key={c.line} className="flex items-center gap-2">
                        <span className="inline-flex h-6 w-12 shrink-0 items-center justify-center rounded text-[11px] font-bold" style={{ background: c.background_color, color: c.text_color }}>Aa</span>
                        <span className="min-w-0 flex-1 truncate text-ink-700">{c.text}</span>
                        <span className={cx('tabular-nums', c.passes ? 'text-pine-700' : 'font-medium text-red-700')}>{c.ratio}:1</span>
                        <span className="w-16 text-right text-[11.5px] text-ink-400">needs {c.threshold}</span>
                        {c.uncertain && <span className="text-[11px] text-amber-700" title="Background varies behind this text">uncertain</span>}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-[12px] leading-snug text-ink-500">Glyph and background colours are estimated by splitting each text box into its two dominant colours. Gradients and photos make this less reliable.</p>
                </section>
                {visual.palette && (
                  <section>
                    <h4 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-400">Palette (CIE ΔE to nearest brand colour, limit {visual.palette.threshold_delta_e})</h4>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {visual.palette.colours.map((c) => (
                        <div key={c.hex} className={cx('w-[88px] rounded-md border p-1.5', c.on_palette ? 'border-line' : 'border-red-300 bg-red-50/50')}>
                          <div className="h-8 rounded" style={{ background: c.hex }} />
                          <p className="mt-1 font-mono text-[11px] text-ink-700">{c.hex}</p>
                          <p className="text-[11px] text-ink-500">{Math.round(c.share * 100)}% · {c.neutral ? 'neutral' : `ΔE ${c.delta_e}`}</p>
                        </div>
                      ))}
                    </div>
                  </section>
                )}
                {visual.logo && (
                  <section>
                    <h4 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-400">Reference logo</h4>
                    <p className="mt-1 text-ink-700">
                      <span className="font-medium">{visual.logo.status.replace('_', ' ')}</span>
                      {visual.logo.score !== undefined && <> · similarity {visual.logo.score}</>}
                    </p>
                    <p className="mt-1 text-[12px] leading-snug text-ink-500">{visual.logo.detail}</p>
                  </section>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
