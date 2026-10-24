import React from 'react';
import { Trash2 } from 'lucide-react';
import { CONTENT_TYPES, StatusPill, timeAgo } from './ui';
import type { ContentItem } from '../types';

interface ContentTableProps {
  items: ContentItem[];
  onOpen: (id: string) => void;
  onDelete?: (item: ContentItem) => void;
  empty: React.ReactNode;
}

/** Compact, keyboard-accessible table of content items. */
export function ContentTable({ items, onOpen, onDelete, empty }: ContentTableProps) {
  if (items.length === 0) return <>{empty}</>;
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-white">
      <table className="w-full text-left text-[13.5px]">
        <thead>
          <tr className="border-b border-line text-[12px] text-ink-500">
            <th className="px-4 py-2 font-medium">Title</th>
            <th className="hidden px-4 py-2 font-medium md:table-cell">Channel</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="hidden px-4 py-2 text-right font-medium sm:table-cell">Updated</th>
            {onDelete && <th className="w-10" aria-label="Actions" />}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {items.map((i) => (
            <tr
              key={i.id}
              tabIndex={0}
              onClick={() => onOpen(i.id)}
              onKeyDown={(e) => e.key === 'Enter' && onOpen(i.id)}
              className="cursor-pointer outline-none hover:bg-ink-50 focus-visible:bg-ink-50"
            >
              <td className="px-4 py-2.5">
                <div className="font-medium text-ink-900">{i.title}</div>
                <div className="text-[12px] text-ink-500">
                  v{i.current_version_number} · {i.created_by}
                </div>
              </td>
              <td className="hidden px-4 py-2.5 text-ink-600 md:table-cell">{CONTENT_TYPES[i.content_type] ?? i.content_type}</td>
              <td className="px-4 py-2.5">
                <StatusPill status={i.status} />
              </td>
              <td className="hidden px-4 py-2.5 text-right tabular-nums text-ink-500 sm:table-cell">{timeAgo(i.updated_at)}</td>
              {onDelete && (
                <td className="pr-2 text-right">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(i);
                    }}
                    className="rounded p-1.5 text-ink-400 hover:bg-red-50 hover:text-red-700"
                    aria-label={`Delete ${i.title}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
