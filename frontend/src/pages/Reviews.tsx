import { useCallback, useEffect, useState } from 'react';
import { Plus, Search } from 'lucide-react';
import { Button, EmptyState, Page, PageHeader, Skeleton, Tabs, inputCls, useConfirm, useToast } from '../components/ui';
import { ContentTable } from '../components/ContentTable';
import type { Brand, ContentItem } from '../types';
import { api } from '../api';

type Filter = 'all' | 'draft' | 'in_review' | 'changes_requested' | 'approved' | 'rejected';

export function Reviews({ brand, navigate, onChanged }: { brand: Brand; navigate: (page: string, id?: string | null) => void; onChanged: () => void }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [items, setItems] = useState<ContentItem[] | null>(null);
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');

  const load = useCallback(() => {
    api.getContentItems(brand.id).then(setItems).catch((e) => toast(e.message, 'error'));
  }, [brand.id, toast]);
  useEffect(() => {
    setItems(null);
    load();
  }, [load]);

  const remove = async (item: ContentItem) => {
    const ok = await confirm({
      title: `Delete “${item.title}”?`,
      body: 'All versions, findings, and comments for this piece are removed. A deletion event stays in the audit trail.',
      confirmLabel: 'Delete',
      danger: true,
    });
    if (!ok) return;
    try {
      await api.deleteContentItem(item.id);
      toast('Deleted.', 'info');
      load();
      onChanged();
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  const count = (f: Filter) => (items ?? []).filter((i) => f === 'all' || i.status === f).length;
  const q = query.trim().toLowerCase();
  const shown = (items ?? []).filter((i) => (filter === 'all' || i.status === filter) && (!q || i.title.toLowerCase().includes(q) || i.created_by.toLowerCase().includes(q)));

  return (
    <Page>
      <PageHeader
        title="Content reviews"
        description="Every piece checked in this workspace, with its current status."
        actions={
          <Button variant="primary" onClick={() => navigate('studio')}>
            <Plus className="h-3.5 w-3.5" /> New review
          </Button>
        }
      />

      <div className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <Tabs
            value={filter}
            onChange={setFilter}
            items={[
              { id: 'all', label: 'All', count: count('all') },
              { id: 'draft', label: 'Drafts', count: count('draft') },
              { id: 'in_review', label: 'In review', count: count('in_review') },
              { id: 'changes_requested', label: 'Changes requested', count: count('changes_requested') },
              { id: 'approved', label: 'Approved', count: count('approved') },
              { id: 'rejected', label: 'Rejected', count: count('rejected') },
            ]}
          />
          <div className="relative sm:w-64">
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-ink-400" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search title or author" aria-label="Search" className={`${inputCls} pl-8`} />
          </div>
        </div>

        {items === null ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <ContentTable
            items={shown}
            onOpen={(id) => navigate('studio', id)}
            onDelete={remove}
            empty={
              items.length === 0 ? (
                <EmptyState title="No content yet" body="Paste some copy into a new review to check it against the rulebook." action={<Button variant="primary" onClick={() => navigate('studio')}>New review</Button>} />
              ) : (
                <EmptyState title="Nothing matches" body="Try another filter or search term." />
              )
            }
          />
        )}
      </div>
    </Page>
  );
}
