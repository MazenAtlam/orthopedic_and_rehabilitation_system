import { create } from 'zustand';

export type ViewerTool = 'PAN' | 'ZOOM' | 'WW_WL' | 'MEASURE' | 'ANNOTATE';
export type ViewLayout = 'SINGLE_2D' | 'MPR' | 'VOLUME_3D' | 'COMPARE';
export type ImageFilter = 'NONE' | 'SHARPEN' | 'SMOOTH' | 'DENOISE';

export interface DicomAnnotation {
  id: string;
  x: number;
  y: number;
  label: string;
  measurement?: string;
}

interface DicomToolState {
  activeTool: ViewerTool;
  layout: ViewLayout;
  filter: ImageFilter;
  windowWidth: number;
  windowLevel: number;
  zoom: number;
  rotation: number;
  pan: { x: number; y: number };
  sliceIndex: number;
  invert: boolean;
  showCdssOverlay: boolean;
  annotations: DicomAnnotation[];

  setActiveTool: (tool: ViewerTool) => void;
  setLayout: (layout: ViewLayout) => void;
  setFilter: (filter: ImageFilter) => void;
  setWindowLevel: (ww: number, wl: number) => void;
  setZoom: (zoom: number) => void;
  rotateBy: (deg: number) => void;
  setPan: (pan: { x: number; y: number }) => void;
  setSliceIndex: (idx: number) => void;
  toggleInvert: () => void;
  toggleCdssOverlay: () => void;
  addAnnotation: (ann: DicomAnnotation) => void;
  resetView: () => void;
}

export const useDicomToolStore = create<DicomToolState>((set) => ({
  activeTool: 'WW_WL',
  layout: 'SINGLE_2D',
  filter: 'NONE',
  windowWidth: 1500,
  windowLevel: -600,
  zoom: 1,
  rotation: 0,
  pan: { x: 0, y: 0 },
  sliceIndex: 42,
  invert: false,
  showCdssOverlay: true,
  annotations: [
    {
      id: 'ann-1',
      x: 36,
      y: 38,
      label: 'RUL Pulmonary Nodule',
      measurement: '6.2 mm',
    },
  ],

  setActiveTool: (activeTool) => set({ activeTool }),
  setLayout: (layout) => set({ layout }),
  setFilter: (filter) => set({ filter }),
  setWindowLevel: (windowWidth, windowLevel) => set({ windowWidth, windowLevel }),
  setZoom: (zoom) => set({ zoom: Math.max(0.5, Math.min(4, zoom)) }),
  rotateBy: (deg) => set((s) => ({ rotation: (s.rotation + deg) % 360 })),
  setPan: (pan) => set({ pan }),
  setSliceIndex: (sliceIndex) => set({ sliceIndex: Math.max(1, Math.min(120, sliceIndex)) }),
  toggleInvert: () => set((s) => ({ invert: !s.invert })),
  toggleCdssOverlay: () => set((s) => ({ showCdssOverlay: !s.showCdssOverlay })),
  addAnnotation: (ann) => set((s) => ({ annotations: [...s.annotations, ann] })),
  resetView: () =>
    set({
      windowWidth: 1500,
      windowLevel: -600,
      zoom: 1,
      rotation: 0,
      pan: { x: 0, y: 0 },
      invert: false,
      filter: 'NONE',
    }),
}));
