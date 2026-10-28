import { useCallback, useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { NewBrandModal } from './components/NewBrandModal';
import { Button, ConfirmProvider, Logo, setActorName, ToastProvider, useConfirm, useToast, type Role } from './components/ui';
import { Overview } from './pages/Overview';
import { Reviews } from './pages/Reviews';
import { Studio } from './pages/Studio';
import { Rulebook } from './pages/Rulebook';
import { Approvals } from './pages/Approvals';
import { Audit } from './pages/Audit';
import { Insights } from './pages/Insights';
import { Settings } from './pages/Settings';
import { Login } from './pages/Login';
import { Governance } from './pages/Governance';
import { Sources } from './pages/Sources';
import { BrandDna } from './pages/BrandDna';
import { Campaigns } from './pages/Campaigns';
import { Replay } from './pages/Replay';
import { NewCreative } from './pages/NewCreative';
import type { Brand, Me } from './types';
import { api, type HealthStatus } from './api';

const PAGES = ['overview', 'reviews', 'studio', 'creative', 'rulebook', 'sources', 'dna', 'campaigns', 'approvals', 'audit', 'insights', 'governance', 'settings', 'replay'];
type Route = { page: string; id: string | null; tab?: string | null };

/** Hash routes (#/studio/<id>) so every screen survives a refresh and can be linked. */
function parseHash(): Route {
  const [, page, id] = (window.location.hash.replace(/^#/, '') || '/overview').split('/');
  const [cleanId, query] = (id || '').split('?');
  const tab = new URLSearchParams(query || '').get('tab');
  return { page: PAGES.includes(page) ? page : 'overview', id: cleanId || null, tab };
}

function Shell() {
  const toast = useToast();
  const confirm = useConfirm();
  const [route, setRoute] = useState<Route>(parseHash);
  const [me, setMe] = useState<Me | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [brand, setBrand] = useState<Brand | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [queueCount, setQueueCount] = useState(0);
  const [navOpen, setNavOpen] = useState(false);
  const [newBrandOpen, setNewBrandOpen] = useState(false);
  const [boot, setBoot] = useState<'loading' | 'ready' | 'error' | 'signed_out'>('loading');

  useEffect(() => {
    const onHash = () => {
      setRoute(parseHash());
      setNavOpen(false);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // Any 401 from the API (expired or revoked session) returns to the sign-in screen.
  useEffect(() => {
    const onUnauthorized = () => {
      setMe(null);
      setBoot('signed_out');
    };
    window.addEventListener('auditra:unauthorized', onUnauthorized);
    return () => window.removeEventListener('auditra:unauthorized', onUnauthorized);
  }, []);

  const navigate = useCallback((page: string, id?: string | null, replace = false) => {
    const hash = `#/${page}${id ? `/${id}` : ''}`;
    if (replace) window.history.replaceState(null, '', hash);
    else if (window.location.hash !== hash) window.location.hash = hash;
    const [cleanId, query] = (id ?? '').split('?');
    setRoute({ page, id: cleanId || null, tab: new URLSearchParams(query || '').get('tab') });
    setNavOpen(false);
  }, []);

  const refreshQueue = useCallback(() => {
    if (!brand) return;
    api.getContentItems(brand.id, 'in_review').then((i) => setQueueCount(i.length)).catch(() => undefined);
  }, [brand]);

  const loadWorkspace = useCallback(async (user: Me) => {
    setMe(user);
    setActorName(user.display_name);
    const [list, h] = await Promise.all([api.getBrands(), api.health().catch(() => null)]);
    setBrands(list);
    setHealth(h);
    let saved: string | null = null;
    try {
      saved = localStorage.getItem('auditra.brand');
    } catch {
      saved = null;
    }
    setBrand(list.find((b) => b.id === saved) ?? list.find((b) => b.is_sample) ?? list[0] ?? null);
    setBoot('ready');
  }, []);

  const load = useCallback(async () => {
    setBoot('loading');
    try {
      const user = await api.me();
      await loadWorkspace(user);
    } catch (e: any) {
      if (/sign in/i.test(e.message) || /401/.test(e.message)) setBoot('signed_out');
      else setBoot('error');
    }
  }, [loadWorkspace]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!brand) return;
    try {
      localStorage.setItem('auditra.brand', brand.id);
    } catch {
      /* storage unavailable: the choice just isn't remembered */
    }
    refreshQueue();
  }, [brand, refreshQueue]);

  const signOut = async () => {
    await api.logout().catch(() => undefined);
    setMe(null);
    setBrand(null);
    setBrands([]);
    setBoot('signed_out');
    navigate('overview', null, true);
  };

  const selectBrand = (b: Brand) => {
    setBrand(b);
    if (['studio', 'replay', 'sources', 'campaigns'].includes(route.page)) navigate('overview');
  };

  const resetDemo = async () => {
    const ok = await confirm({
      title: 'Reset the demo workspace?',
      body: 'Northstar goes back to its starting rules, sources, policies and sample content for everyone using the demo. Changes made in it are removed.',
      confirmLabel: 'Reset',
      danger: true,
    });
    if (!ok) return;
    try {
      const sample = await api.resetSampleBrand();
      const list = await api.getBrands();
      setBrands(list);
      setBrand(list.find((b) => b.id === sample.id) ?? sample);
      navigate('overview');
      toast('Demo workspace reset.', 'success');
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  if (boot === 'loading') {
    return <div className="flex h-full items-center justify-center text-[13px] text-ink-500">Loading…</div>;
  }

  if (boot === 'signed_out' || !me) {
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
    return <Login onSignedIn={(u) => loadWorkspace(u).then(() => toast(`Signed in as ${u.display_name}.`, 'success')).catch(() => setBoot('error'))} />;
  }

  const role: Role = (me.memberships.find((m) => m.brand_id === brand?.id)?.role ?? 'creator') as Role;

  if (!brand) {
    return (
      <div className="flex h-full items-center justify-center px-6">
        <div className="w-full max-w-md">
          <Logo />
          <h1 className="mt-8 text-[26px] font-semibold leading-tight text-ink-900">Welcome, {me.display_name}.</h1>
          <p className="mt-3 text-[14px] leading-relaxed text-ink-600">
            You are not a member of any workspace yet. Create one for your brand (you become its admin), or sign out and use a demo persona to explore the fictional Northstar workspace.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            <Button variant="primary" onClick={() => setNewBrandOpen(true)}>Create a workspace</Button>
            <Button onClick={signOut}>Sign out</Button>
          </div>
        </div>
        <NewBrandModal
          open={newBrandOpen}
          onClose={() => setNewBrandOpen(false)}
          onCreated={async (b) => {
            const fresh = await api.me();
            setMe(fresh);
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
        return <Studio brand={brand} contentId={route.id} initialTab={route.tab ?? undefined} role={role} navigate={navigate} onChanged={refreshQueue} />;
      case 'creative':
        return <NewCreative brand={brand} canCreate={role !== 'reviewer'} navigate={navigate} />;
      case 'rulebook':
        return <Rulebook brand={brand} />;
      case 'sources':
        return <Sources brand={brand} role={role} docId={route.id} navigate={navigate} />;
      case 'dna':
        return <BrandDna brand={brand} role={role} navigate={navigate} />;
      case 'campaigns':
        return <Campaigns brand={brand} canManage={role !== 'reviewer'} campaignId={route.id} navigate={navigate} />;
      case 'replay':
        return <Replay contentId={route.id} role={role} navigate={navigate} />;
      case 'approvals':
        return <Approvals brand={brand} role={role} navigate={navigate} onChanged={refreshQueue} />;
      case 'audit':
        return <Audit brand={brand} navigate={navigate} />;
      case 'insights':
        return <Insights brand={brand} />;
      case 'governance':
        return <Governance brand={brand} role={role} me={me.display_name} />;
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
        me={me}
        onSignOut={signOut}
        queueCount={queueCount}
        open={navOpen}
        onClose={() => setNavOpen(false)}
        hasId={!!route.id}
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
        onCreated={async (b) => {
          setMe(await api.me());
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
