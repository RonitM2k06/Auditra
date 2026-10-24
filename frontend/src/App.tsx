import { useCallback, useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { NewBrandModal } from './components/NewBrandModal';
import { ACTORS, Button, ConfirmProvider, Logo, ToastProvider, useConfirm, useToast, type Role } from './components/ui';
import { Overview } from './pages/Overview';
import { Reviews } from './pages/Reviews';
import { Studio } from './pages/Studio';
import { Rulebook } from './pages/Rulebook';
import { Approvals } from './pages/Approvals';
import { Audit } from './pages/Audit';
import { Insights } from './pages/Insights';
import { Settings } from './pages/Settings';
import type { Brand } from './types';
import { api, type HealthStatus } from './api';

const PAGES = ['overview', 'reviews', 'studio', 'rulebook', 'approvals', 'audit', 'insights', 'settings'];
type Route = { page: string; id: string | null };

/** Hash routes (#/studio/<id>) so every screen survives a refresh and can be linked. */
function parseHash(): Route {
  const [, page, id] = (window.location.hash.replace(/^#/, '') || '/overview').split('/');
  return { page: PAGES.includes(page) ? page : 'overview', id: id || null };
}

function Shell() {
  const toast = useToast();
  const confirm = useConfirm();
  const [route, setRoute] = useState<Route>(parseHash);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [brand, setBrand] = useState<Brand | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [role, setRoleState] = useState<Role>(() => {
    const stored = localStorage.getItem('auditra.role');
    return stored && stored in ACTORS ? (stored as Role) : 'creator';
  });
  const [queueCount, setQueueCount] = useState(0);
  const [navOpen, setNavOpen] = useState(false);
  const [newBrandOpen, setNewBrandOpen] = useState(false);
  const [boot, setBoot] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    const onHash = () => {
      setRoute(parseHash());
      setNavOpen(false);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const navigate = useCallback((page: string, id?: string | null, replace = false) => {
    const hash = `#/${page}${id ? `/${id}` : ''}`;
    if (replace) window.history.replaceState(null, '', hash);
    else if (window.location.hash !== hash) window.location.hash = hash;
    setRoute({ page, id: id ?? null });
    setNavOpen(false);
  }, []);

  const refreshQueue = useCallback(() => {
    if (!brand) return;
    api.getContentItems(brand.id, 'in_review').then((i) => setQueueCount(i.length)).catch(() => undefined);
  }, [brand]);

  const load = useCallback(async () => {
    setBoot('loading');
    try {
      const [list, h] = await Promise.all([api.getBrands(), api.health().catch(() => null)]);
      setBrands(list);
      setHealth(h);
      const saved = localStorage.getItem('auditra.brand');
      setBrand(list.find((b) => b.id === saved) ?? list.find((b) => b.is_sample) ?? list[0] ?? null);
      setBoot('ready');
    } catch {
      setBoot('error');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!brand) return;
    localStorage.setItem('auditra.brand', brand.id);
    refreshQueue();
  }, [brand, refreshQueue]);

  const setRole = (r: Role) => {
    setRoleState(r);
    localStorage.setItem('auditra.role', r);
    toast(`Now acting as ${ACTORS[r].name}, ${ACTORS[r].role.toLowerCase()}.`, 'info');
  };

  const selectBrand = (b: Brand) => {
    setBrand(b);
    if (route.page === 'studio') navigate('reviews');
  };

  const resetDemo = async () => {
    const ok = await confirm({
      title: 'Reset the demo workspace?',
      body: 'Northstar goes back to its starting rules, claims, and sample content. Changes you made in it are removed.',
      confirmLabel: 'Reset',
      danger: true,
    });
    if (!ok) return;
    try {
      const sample = await api.resetSampleBrand();
      const list = await api.getBrands();
      setBrands(list);
      setBrand(sample);
      navigate('overview');
      toast('Demo workspace reset.', 'success');
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  if (boot === 'loading') {
    return <div className="flex h-full items-center justify-center text-[13px] text-ink-500">Loading workspace…</div>;
  }

  if (boot === 'error') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
        <Logo />
        <p className="mt-2 text-[14px] text-ink-800">Can’t reach the Auditra server.</p>
        <p className="max-w-sm text-[13px] text-ink-500">Check that the backend is running, then try again.</p>
        <Button onClick={load}>Try again</Button>
      </div>
    );
  }

  if (!brand) {
    return (
      <div className="flex h-full items-center justify-center px-6">
        <div className="w-full max-w-md">
          <Logo />
          <h1 className="mt-8 font-serif text-[28px] leading-tight text-ink-900">Check content against your brand rules before it ships.</h1>
          <p className="mt-3 text-[14px] leading-relaxed text-ink-600">
            Start with the Northstar demo (a fictional brand with rules and sample copy already set up) or create an empty workspace for your own brand.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            <Button
              variant="primary"
              onClick={async () => {
                try {
                  const b = await api.resetSampleBrand();
                  setBrands([b]);
                  setBrand(b);
                } catch (e: any) {
                  toast(e.message, 'error');
                }
              }}
            >
              Open the demo workspace
            </Button>
            <Button onClick={() => setNewBrandOpen(true)}>Create a workspace</Button>
          </div>
        </div>
        <NewBrandModal
          open={newBrandOpen}
          onClose={() => setNewBrandOpen(false)}
          onCreated={(b) => {
            setBrands([b]);
            setBrand(b);
            navigate('rulebook');
          }}
        />
      </div>
    );
  }

  const page = () => {
    switch (route.page) {
      case 'reviews':
        return <Reviews brand={brand} navigate={navigate} onChanged={refreshQueue} />;
      case 'studio':
        return <Studio brand={brand} contentId={route.id} role={role} navigate={navigate} onChanged={refreshQueue} />;
      case 'rulebook':
        return <Rulebook brand={brand} />;
      case 'approvals':
        return <Approvals brand={brand} role={role} navigate={navigate} onChanged={refreshQueue} />;
      case 'audit':
        return <Audit brand={brand} navigate={navigate} />;
      case 'insights':
        return <Insights brand={brand} />;
      case 'settings':
        return (
          <Settings
            brand={brand}
            health={health}
            onResetDemo={resetDemo}
            onBrandUpdated={(b) => {
              setBrand(b);
              setBrands((list) => list.map((x) => (x.id === b.id ? b : x)));
            }}
          />
        );
      default:
        return <Overview brand={brand} navigate={navigate} />;
    }
  };

  return (
    <div className="flex h-full">
      <Sidebar
        page={route.page}
        navigate={navigate}
        brands={brands}
        brand={brand}
        onSelectBrand={selectBrand}
        onNewBrand={() => setNewBrandOpen(true)}
        role={role}
        setRole={setRole}
        queueCount={queueCount}
        open={navOpen}
        onClose={() => setNavOpen(false)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar brand={brand} page={route.page} onMenu={() => setNavOpen(true)} health={health} />
        <main key={brand.id} className="flex min-h-0 flex-1 flex-col">
          {page()}
        </main>
      </div>
      <NewBrandModal
        open={newBrandOpen}
        onClose={() => setNewBrandOpen(false)}
        onCreated={(b) => {
          setBrands((list) => [b, ...list]);
          setBrand(b);
          navigate('rulebook');
        }}
      />
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <ConfirmProvider>
        <Shell />
      </ConfirmProvider>
    </ToastProvider>
  );
}
