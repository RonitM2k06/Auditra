import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Navbar } from './components/Navbar';
import { OverviewDashboard } from './components/OverviewDashboard';
import { ContentReviewsList } from './components/ContentReviewsList';
import { ReviewStudio } from './components/ReviewStudio';
import { BrandRulebook } from './components/BrandRulebook';
import { ApprovalQueue } from './components/ApprovalQueue';
import { AuditTrail } from './components/AuditTrail';
import { GovernanceInsights } from './components/GovernanceInsights';
import { SettingsView } from './components/SettingsView';
import { NewBrandModal } from './components/NewBrandModal';
import { ToastContainer, ToastMessage } from './components/Toast';
import { Brand } from './types';
import { api } from './api';

export function App() {
  const [currentTab, setCurrentTab] = useState<string>('overview');
  const [brands, setBrands] = useState<Brand[]>([]);
  const [selectedBrand, setSelectedBrand] = useState<Brand | null>(null);
  const [activeContentId, setActiveContentId] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<'creator' | 'reviewer' | 'admin'>('creator');
  const [pendingApprovalCount, setPendingApprovalCount] = useState<number>(0);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [showNewBrandModal, setShowNewBrandModal] = useState<boolean>(false);
  const [bootstrapping, setBootstrapping] = useState<boolean>(true);

  // Toast helper
  const showToast = (text: string, type: 'success' | 'error' | 'info' = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, text, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Initial load
  useEffect(() => {
    bootstrapApp();
  }, []);

  const bootstrapApp = async () => {
    setBootstrapping(true);
    try {
      const brandList = await api.getBrands();
      setBrands(brandList);
      if (brandList.length > 0) {
        // Prefer sample brand Northstar or first brand
        const defaultBrand = brandList.find((b) => b.is_sample) || brandList[0];
        setSelectedBrand(defaultBrand);
        fetchQueueCount(defaultBrand.id);
      }
    } catch (err: any) {
      showToast(err.message || 'Error connecting to AUDITRA API', 'error');
    } finally {
      setBootstrapping(false);
    }
  };

  const fetchQueueCount = async (brandId: string) => {
    try {
      const items = await api.getContentItems(brandId, 'in_review');
      setPendingApprovalCount(items.length);
    } catch (_) {}
  };

  const handleResetSample = async () => {
    if (!window.confirm("Reset 'Northstar Cloud' demo workspace to default state?")) return;
    try {
      const sample = await api.resetSampleBrand();
      showToast("Reset 'Northstar Cloud' workspace with 7 rules, 3 claims, and demo content", 'success');
      const refreshedList = await api.getBrands();
      setBrands(refreshedList);
      setSelectedBrand(sample);
      fetchQueueCount(sample.id);
      setCurrentTab('overview');
    } catch (err: any) {
      showToast(err.message || 'Failed to reset sample workspace', 'error');
    }
  };

  const handleOpenContentInStudio = (contentId: string) => {
    setActiveContentId(contentId);
    setCurrentTab('studio');
  };

  const handleNewReview = () => {
    setActiveContentId(null);
    setCurrentTab('studio');
  };

  if (bootstrapping) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-navy-950 text-white font-sans">
        <div className="w-10 h-10 border-3 border-brand-500 border-t-transparent rounded-full animate-spin mb-4" />
        <div className="text-sm font-semibold tracking-wide text-brand-400">INITIALIZING AUDITRA WORKSPACE</div>
        <div className="text-xs text-slate-400 mt-1">Grounded Brand Governance & Review Control Layer</div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface-base font-sans antialiased text-dark-primary">
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        brands={brands}
        selectedBrand={selectedBrand}
        onSelectBrand={(b) => {
          setSelectedBrand(b);
          fetchQueueCount(b.id);
        }}
        userRole={userRole}
        setUserRole={setUserRole}
        pendingApprovalCount={pendingApprovalCount}
        onResetSample={handleResetSample}
        onOpenNewBrandModal={() => setShowNewBrandModal(true)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navbar */}
        <Navbar
          currentTab={currentTab}
          selectedBrand={selectedBrand}
          userRole={userRole}
          onNewReviewClick={handleNewReview}
        />

        {/* View Router */}
        {selectedBrand && (
          <main className="flex-1 flex overflow-hidden">
            {currentTab === 'overview' && (
              <OverviewDashboard
                brand={selectedBrand}
                onOpenContent={handleOpenContentInStudio}
                onNavigateTab={setCurrentTab}
                showToast={showToast}
              />
            )}

            {currentTab === 'reviews' && (
              <ContentReviewsList
                brand={selectedBrand}
                onOpenContent={handleOpenContentInStudio}
                onNewReview={handleNewReview}
                showToast={showToast}
              />
            )}

            {currentTab === 'studio' && (
              <ReviewStudio
                contentId={activeContentId}
                brandId={selectedBrand.id}
                userRole={userRole}
                onReviewCompleted={() => fetchQueueCount(selectedBrand.id)}
                onNavigateToReviews={() => setCurrentTab('reviews')}
                showToast={showToast}
              />
            )}

            {currentTab === 'rulebook' && (
              <BrandRulebook brand={selectedBrand} showToast={showToast} />
            )}

            {currentTab === 'approvals' && (
              <ApprovalQueue
                brand={selectedBrand}
                userRole={userRole}
                onOpenContent={handleOpenContentInStudio}
                showToast={showToast}
              />
            )}

            {currentTab === 'audit' && (
              <AuditTrail brand={selectedBrand} showToast={showToast} />
            )}

            {currentTab === 'insights' && (
              <GovernanceInsights brand={selectedBrand} showToast={showToast} />
            )}

            {currentTab === 'settings' && (
              <SettingsView
                brand={selectedBrand}
                onBrandUpdated={(updated) => {
                  setSelectedBrand(updated);
                  setBrands(brands.map((b) => (b.id === updated.id ? updated : b)));
                }}
                onResetSample={handleResetSample}
                showToast={showToast}
              />
            )}
          </main>
        )}
      </div>

      {/* New Brand Modal */}
      <NewBrandModal
        isOpen={showNewBrandModal}
        onClose={() => setShowNewBrandModal(false)}
        onBrandCreated={(newB) => {
          setBrands([newB, ...brands]);
          setSelectedBrand(newB);
        }}
        showToast={showToast}
      />

      {/* Floating Notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

export default App;
