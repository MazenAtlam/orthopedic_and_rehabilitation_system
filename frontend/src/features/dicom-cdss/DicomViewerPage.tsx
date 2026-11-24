import React, { useState } from 'react';
import {
  ZoomIn,
  Move,
  RotateCw,
  SunMedium,
  Ruler,
  MessageSquarePlus,
  Layers,
  Box,
  Columns2,
  Square,
  BrainCircuit,
  RotateCcw,
  Save,
  Contrast,
} from 'lucide-react';
import {
  useDicomToolStore,
  ViewerTool,
  ViewLayout,
  ImageFilter,
} from '../../store/dicomToolStore';
import { usePermissions } from '../../hooks/usePermissions';

const WW_WL_PRESETS = [
  { name: 'Lung', ww: 1500, wl: -600 },
  { name: 'Soft Tissue', ww: 400, wl: 40 },
  { name: 'Bone', ww: 2000, wl: 300 },
  { name: 'Brain', ww: 80, wl: 40 },
];

export const DicomViewerPage: React.FC = () => {
  const { isClinical } = usePermissions();
  const store = useDicomToolStore();
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [savedNotice, setSavedNotice] = useState(false);

  // Compute CSS visual approximation of WW/WL & filters for live preview
  const contrastPct = Math.max(40, Math.min(240, Math.round((2000 / store.windowWidth) * 100)));
  const brightnessPct = Math.max(40, Math.min(180, Math.round(100 + store.windowLevel / 15)));
  const filterCss = [
    `contrast(${contrastPct}%)`,
    `brightness(${brightnessPct}%)`,
    store.invert ? 'invert(100%)' : '',
    store.filter === 'SMOOTH' ? 'blur(1px)' : '',
    store.filter === 'DENOISE' ? 'blur(0.5px) contrast(108%)' : '',
    store.filter === 'SHARPEN' ? 'contrast(135%)' : '',
  ]
    .filter(Boolean)
    .join(' ');

  const handleViewportMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const xPct = Math.round(((e.clientX - rect.left) / rect.width) * 100);
    const yPct = Math.round(((e.clientY - rect.top) / rect.height) * 100);

    if (store.activeTool === 'ANNOTATE' && isClinical) {
      const note = window.prompt('Enter clinical annotation note:');
      if (note) {
        store.addAnnotation({ id: `ann-${Date.now()}`, x: xPct, y: yPct, label: note });
      }
      return;
    }

    if (store.activeTool === 'MEASURE' && isClinical) {
      const dist = (Math.random() * 12 + 2).toFixed(1);
      store.addAnnotation({
        id: `meas-${Date.now()}`,
        x: xPct,
        y: yPct,
        label: 'ROI Length',
        measurement: `${dist} mm`,
      });
      return;
    }

    setIsDragging(true);
    setDragStart({ x: e.clientX - store.pan.x, y: e.clientY - store.pan.y });
  };

  const handleViewportMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    if (store.activeTool === 'PAN') {
      store.setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    } else if (store.activeTool === 'WW_WL') {
      const deltaX = e.movementX * 8;
      const deltaY = -e.movementY * 4;
      store.setWindowLevel(
        Math.max(50, store.windowWidth + deltaX),
        Math.max(-1000, Math.min(1000, store.windowLevel + deltaY))
      );
    }
  };

  const handleSaveToRecord = () => {
    setSavedNotice(true);
    setTimeout(() => setSavedNotice(false), 3000);
  };

  // Simulated anatomical SVG slice renderer
  const renderScanCanvas = (planeLabel: string, sliceOffset = 0) => {
    const currentSlice = Math.min(120, Math.max(1, store.sliceIndex + sliceOffset));
    const scaleFactor = 0.85 + Math.sin((currentSlice / 120) * Math.PI) * 0.25;

    return (
      <div
        onMouseDown={handleViewportMouseDown}
        onMouseMove={handleViewportMouseMove}
        onMouseUp={() => setIsDragging(false)}
        onMouseLeave={() => setIsDragging(false)}
        onWheel={(e) => store.setSliceIndex(store.sliceIndex + (e.deltaY > 0 ? 1 : -1))}
        className="relative bg-black rounded-lg overflow-hidden border border-slate-800 flex items-center justify-center select-none cursor-crosshair h-full min-h-[340px]"
      >
        {/* Top-left DICOM Metadata Overlay */}
        <div className="absolute top-3 left-3 z-10 text-[11px] font-mono text-cyan-300/90 pointer-events-none space-y-0.5">
          <p>HASSAN, OMAR (MRN-884920)</p>
          <p>MODALITY: CT CHEST • {planeLabel}</p>
          <p>SLICE: {currentSlice} / 120</p>
        </div>

        {/* Bottom-left WW/WL Overlay */}
        <div className="absolute bottom-3 left-3 z-10 text-[11px] font-mono text-amber-300/90 pointer-events-none">
          WW: {store.windowWidth} | WL: {store.windowLevel} | ZOOM: {store.zoom.toFixed(2)}x
        </div>

        {/* Simulated DICOM Slice Graphic */}
        <div
          style={{
            transform: `translate(${store.pan.x}px, ${store.pan.y}px) scale(${store.zoom * scaleFactor}) rotate(${store.rotation}deg)`,
            filter: filterCss,
          }}
          className="transition-transform duration-75"
        >
          <svg width="280" height="280" viewBox="0 0 280 280">
            {/* Thorax Outer Wall */}
            <ellipse cx="140" cy="140" rx="118" ry="96" fill="#1e293b" stroke="#94a3b8" strokeWidth="6" />
            {/* Ribs */}
            <ellipse cx="140" cy="140" rx="108" ry="86" fill="none" stroke="#e2e8f0" strokeWidth="3" strokeDasharray="14 8" />
            {/* Left & Right Lung Fields */}
            <ellipse cx="96" cy="138" rx="38" ry="56" fill="#090d16" stroke="#475569" strokeWidth="2" />
            <ellipse cx="184" cy="138" rx="38" ry="56" fill="#090d16" stroke="#475569" strokeWidth="2" />
            {/* Spine & Sternum */}
            <circle cx="140" cy="204" r="14" fill="#f8fafc" />
            <rect x="133" y="64" width="14" height="10" rx="3" fill="#e2e8f0" />
            {/* Heart / Mediastinum */}
            <ellipse cx="146" cy="132" rx="22" ry="28" fill="#64748b" />
            {/* Target Pulmonary Nodule */}
            <circle cx="92" cy="112" r="5" fill="#cbd5e1" />
          </svg>
        </div>

        {/* AI CDSS Diagnostic Overlay */}
        {store.showCdssOverlay && planeLabel === 'AXIAL' && (
          <div
            style={{ left: '31%', top: '34%' }}
            className="absolute w-12 h-12 border-2 border-rose-500 bg-rose-500/15 rounded pointer-events-none animate-pulse"
          >
            <span className="absolute -top-5 left-0 bg-rose-600 text-white text-[10px] font-mono px-1.5 py-0.5 rounded whitespace-nowrap">
              AI: Nodule 94.2%
            </span>
          </div>
        )}

        {/* User Annotations & Measurements */}
        {planeLabel === 'AXIAL' &&
          store.annotations.map((ann) => (
            <div
              key={ann.id}
              style={{ left: `${ann.x}%`, top: `${ann.y}%` }}
              className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-none"
            >
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 border border-black" />
              <div className="mt-1 bg-slate-900/90 border border-emerald-500/60 text-emerald-300 text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap">
                {ann.label} {ann.measurement ? `(${ann.measurement})` : ''}
              </div>
            </div>
          ))}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Top Toolbar */}
      <div className="bg-slate-900 text-slate-200 p-3 rounded-xl flex flex-wrap items-center justify-between gap-3">
        {/* Manipulation & Bonus Annotation Tools */}
        <div className="flex flex-wrap items-center gap-1.5">
          {(
            [
              { id: 'WW_WL', label: 'WW/WL', icon: <SunMedium className="w-4 h-4" /> },
              { id: 'PAN', label: 'Pan', icon: <Move className="w-4 h-4" /> },
              { id: 'ZOOM', label: 'Zoom', icon: <ZoomIn className="w-4 h-4" /> },
              { id: 'MEASURE', label: 'Measure', icon: <Ruler className="w-4 h-4" /> },
              { id: 'ANNOTATE', label: 'Annotate', icon: <MessageSquarePlus className="w-4 h-4" /> },
            ] as { id: ViewerTool; label: string; icon: React.ReactNode }[]
          ).map((tool) => (
            <button
              key={tool.id}
              onClick={() => store.setActiveTool(tool.id)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition ${
                store.activeTool === tool.id
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              {tool.icon}
              {tool.label}
            </button>
          ))}

          <button
            onClick={() => store.setZoom(store.zoom + 0.25)}
            className="px-2.5 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700"
          >
            +Zoom
          </button>
          <button
            onClick={() => store.rotateBy(90)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700"
          >
            <RotateCw className="w-3.5 h-3.5" /> 90°
          </button>
          <button
            onClick={store.toggleInvert}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700"
          >
            <Contrast className="w-3.5 h-3.5" /> Invert
          </button>
          <button
            onClick={store.resetView}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-amber-300"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Reset
          </button>
        </div>

        {/* Layout Mode Switcher (2D / MPR / 3D Volume / Bonus Compare) */}
        <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-lg">
          {(
            [
              { id: 'SINGLE_2D', label: '2D', icon: <Square className="w-3.5 h-3.5" /> },
              { id: 'MPR', label: 'MPR', icon: <Layers className="w-3.5 h-3.5" /> },
              { id: 'VOLUME_3D', label: '3D Vol', icon: <Box className="w-3.5 h-3.5" /> },
              { id: 'COMPARE', label: 'Compare', icon: <Columns2 className="w-3.5 h-3.5" /> },
            ] as { id: ViewLayout; label: string; icon: React.ReactNode }[]
          ).map((mode) => (
            <button
              key={mode.id}
              onClick={() => store.setLayout(mode.id)}
              className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium transition ${
                store.layout === mode.id
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {mode.icon}
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Workstation Area: Viewports + Right Controls/CDSS Panel */}
      <div className="grid lg:grid-cols-4 gap-4">
        {/* Viewport Grid (3 cols) */}
        <div className="lg:col-span-3 space-y-3">
          {store.layout === 'SINGLE_2D' && renderScanCanvas('AXIAL')}

          {store.layout === 'MPR' && (
            <div className="grid md:grid-cols-3 gap-3">
              {renderScanCanvas('AXIAL', 0)}
              {renderScanCanvas('SAGITTAL', 18)}
              {renderScanCanvas('CORONAL', -14)}
            </div>
          )}

          {store.layout === 'COMPARE' && (
            <div className="grid md:grid-cols-2 gap-3">
              {renderScanCanvas('AXIAL (Current CT - Nov 2026)', 0)}
              {renderScanCanvas('AXIAL (Prior MRI - May 2026)', -22)}
            </div>
          )}

          {store.layout === 'VOLUME_3D' && (
            <div className="bg-slate-950 rounded-xl border border-slate-800 p-6 min-h-[380px] flex flex-col items-center justify-center text-center space-y-3">
              <Box className="w-14 h-14 text-cyan-400 animate-spin" style={{ animationDuration: '12s' }} />
              <h3 className="text-white font-semibold">3D Volumetric Thoracic Reconstruction</h3>
              <p className="text-xs text-slate-400 max-w-md">
                WebGL VTK/Cornerstone3D volume ray-casting active. Rotate using mouse drag or adjust
                opacity transfer function via WW/WL sliders.
              </p>
            </div>
          )}

          {/* Slice Scrubber Bar */}
          <div className="bg-white px-4 py-2.5 rounded-xl border border-slate-200 flex items-center gap-4">
            <span className="text-xs font-semibold text-slate-600 whitespace-nowrap">
              Slice: {store.sliceIndex} / 120
            </span>
            <input
              type="range"
              min={1}
              max={120}
              value={store.sliceIndex}
              onChange={(e) => store.setSliceIndex(Number(e.target.value))}
              className="w-full accent-blue-600"
            />
          </div>
        </div>

        {/* Right Panel: Enhancement Filters + AI CDSS Diagnostic Support */}
        <div className="space-y-4">
          {/* Image Enhancement & Windowing */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Windowing & Filters
            </h2>
            <div className="grid grid-cols-2 gap-1.5">
              {WW_WL_PRESETS.map((p) => (
                <button
                  key={p.name}
                  onClick={() => store.setWindowLevel(p.ww, p.wl)}
                  className="text-xs py-1.5 px-2 rounded border border-slate-200 hover:border-blue-500 hover:bg-blue-50 font-medium text-slate-700"
                >
                  {p.name}
                </button>
              ))}
            </div>

            <div>
              <label className="block text-xs text-slate-600 mb-1">Enhancement Filter</label>
              <select
                value={store.filter}
                onChange={(e) => store.setFilter(e.target.value as ImageFilter)}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs"
              >
                <option value="NONE">Original (Unfiltered)</option>
                <option value="SHARPEN">Edge Sharpening</option>
                <option value="SMOOTH">Gaussian Smoothing</option>
                <option value="DENOISE">Noise Reduction</option>
              </select>
            </div>
          </div>

          {/* AI CDSS Panel */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-600 flex items-center gap-1.5">
                <BrainCircuit className="w-4 h-4" />
                AI CDSS Insights
              </h2>
              <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={store.showCdssOverlay}
                  onChange={store.toggleCdssOverlay}
                  className="accent-indigo-600"
                />
                Overlay
              </label>
            </div>

            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 space-y-1">
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-rose-900">Pulmonary Nodule (RUL)</span>
                <span className="text-[11px] font-mono bg-rose-600 text-white px-1.5 py-0.5 rounded">
                  94.2%
                </span>
              </div>
              <p className="text-xs text-rose-800">
                6.2 mm solid nodule detected on slice #42. Fleischner guidelines suggest 6–12 month
                follow-up CT.
              </p>
            </div>

            {isClinical && (
              <button
                onClick={handleSaveToRecord}
                className="w-full flex items-center justify-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-white py-2 rounded-lg text-xs font-medium transition"
              >
                <Save className="w-3.5 h-3.5" />
                {savedNotice ? 'Saved to Patient EMR!' : 'Save Annotations to EMR'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};