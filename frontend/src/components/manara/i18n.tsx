'use client';

import * as React from 'react';

/* ============================================================
   MANARA i18n — EN/AR language context + translations
   ============================================================ */

export type Language = 'en' | 'ar';

type Dict = Record<string, string>;

const en: Dict = {
  'app.name': 'MANARA',
  'app.tagline': 'Adaptive Intelligence Factory',
  'app.shortTagline': 'Adaptive Intelligence Factory',

  'home.headline': 'What do you want to {{discover}} today?',
  'home.headline.prefix': 'What do you want to',
  'home.headline.suffix': 'today?',
  'home.headline.accent': 'discover',
  'home.subheadline':
    'Turn your research question into a systematic investigation with evidence-backed analysis, source coverage verification, and honest reporting.',
  'home.placeholder': 'Enter your research question... (minimum 10 characters)',
  'home.submit': 'Start Investigation',
  'home.clear': 'Clear',
  'home.composerLabel': 'Research question',
  'home.composerHint': 'Write a clear, focused question. MANARA will decompose it into information needs and verify source coverage before any evidence is collected.',
  'home.examples.label': 'Try an example',
  'home.examples.1': 'What is the evidence on long-term effects of microplastics in marine ecosystems?',
  'home.examples.2': 'How are additive manufacturing technologies transforming prosthetics?',
  'home.examples.3': 'What are the most cited forecasting methods for renewable energy adoption?',

  'home.step1.title': 'Analyze your question',
  'home.step1.desc': 'We decompose your research query into specific information needs',
  'home.step2.title': 'Assess source coverage',
  'home.step2.desc': 'We check which capabilities and connectors can address each need',
  'home.step3.title': 'Build the investigation path',
  'home.step3.desc': 'We compose a mold that guides evidence collection and analysis',

  'home.composing': 'Composing your investigation mold...',
  'home.composing.sub': 'Detecting information needs · matching capabilities · verifying coverage',
  'home.investigationId': 'Investigation ID',
  'home.moldId': 'Mold Recipe',
  'home.detectedNeeds': 'Detected Research Needs',
  'home.coverage': 'Source Coverage',
  'home.gaps': 'Coverage Gaps',
  'home.complete': 'Complete',
  'home.partial': 'Partial Coverage',
  'home.blocker': 'Coverage Blocker Report',
  'home.blocker.title': 'This question cannot be fully investigated yet',
  'home.blocker.desc':
    'MANARA refuses to fabricate evidence. Some information needs have no operational source connector — we are returning a structured coverage blocker report instead of a research deliverable.',
  'home.workspaceNotice': 'The full Investigation Workspace is scheduled for the next implementation stage.',
  'home.newDomain': 'New Domain',
  'home.newDomainHint': 'No existing mold matched this query — a new domain mold was synthesized.',
  'home.fixtureBadge': 'Development Fixture',
  'home.fixtureHint': 'Backend at localhost:8000 was unreachable — this composition is a deterministic fixture for visual review.',
  'home.deliverable.research_deliverable': 'Research Deliverable',
  'home.deliverable.coverage_blocker_report': 'Coverage Blocker Report',
  'home.deliverableType': 'Deliverable Type',
  'home.selectionReasoning': 'Selection reasoning',
  'home.foundryResolution': 'Foundry resolution',
  'home.resolutionNotes': 'Resolution notes',
  'home.connectorIds': 'Connectors',
  'home.capability': 'Capability',
  'home.relevance': 'relevance',
  'home.need': 'Need',
  'home.catalogComplete': 'Catalog complete',
  'home.catalogComplete.yes': 'Yes — every need has at least a catalog card',
  'home.catalogComplete.no': 'No — some needs are unknown to the catalog',
  'home.composedAt': 'Composed at',
  'home.detectionReasoning': 'Detection reasoning',
  'home.compositionNotes': 'Composition notes',
  'home.startNew': 'Start a new investigation',

  'nav.home': 'Home',
  'nav.workspace': 'Investigation Workspace',
  'nav.memory': 'Memory Explorer',
  'nav.registry': 'Capability Registry',
  'nav.foundry': 'Source Foundry',
  'nav.molds': 'Mold Factory',
  'nav.agents': 'Agent Registry',
  'nav.foresight': 'Foresight',
  'nav.publishing': 'Publishing Studio',
  'nav.comingLater': 'Coming Later',
  'nav.active': 'Active',
  'nav.section.intelligence': 'Intelligence',
  'nav.section.factory': 'Factory',
  'nav.section.studio': 'Studio',

  'demo.mode': 'Single-tenant demo mode',
  'demo.version': 'v0.1 · UI Preview',

  'status.online': 'Online',
  'status.offline': 'Offline (fixture)',
  'status.checking': 'Checking…',

  'error.title': 'Something went wrong',
  'error.retry': 'Retry',
  'error.compose': 'Could not compose the investigation mold.',
  'error.status': 'Could not reach the MANARA service.',

  'header.menu': 'Menu',
  'header.closeMenu': 'Close menu',
  'header.collapseSidebar': 'Collapse sidebar',
  'header.expandSidebar': 'Expand sidebar',
  'header.language': 'Language',
  'header.languageEn': 'English',
  'header.languageAr': 'العربية',
};

const ar: Dict = {
  'app.name': 'منارة',
  'app.tagline': 'مصنع الذكاء التكيفي',
  'app.shortTagline': 'مصنع الذكاء التكيفي',

  'home.headline': 'ماذا تريد أن {{discover}} اليوم؟',
  'home.headline.prefix': 'ماذا تريد أن',
  'home.headline.suffix': 'اليوم؟',
  'home.headline.accent': 'تكتشف',
  'home.subheadline':
    'حوّل سؤالك البحثي إلى تحقيق منهجي مع تحليل مدعوم بالأدلة والتحقق من تغطية المصادر والتقارير الصادقة.',
  'home.placeholder': 'أدخل سؤالك البحثي... (الحد الأدنى 10 أحرف)',
  'home.submit': 'بدء التحقيق',
  'home.clear': 'مسح',
  'home.composerLabel': 'سؤال البحث',
  'home.composerHint':
    'اكتب سؤالاً واضحاً ومركّزاً. ستقوم منارة بتحليله إلى احتياجات معلوماتية والتحقق من تغطية المصادر قبل جمع أي أدلة.',
  'home.examples.label': 'جرّب مثالاً',
  'home.examples.1': 'ما الأدلة حول الآثار طويلة الأمد للمواد البلاستيكية الدقيقة في النظم البيئية البحرية؟',
  'home.examples.2': 'كيف تُحوّل تقنيات التصنيع التراكمي مجال الأطراف الاصطناعية؟',
  'home.examples.3': 'ما أكثر طرق التنبؤ باعتماد الطاقة المتجددة استشهاداً؟',

  'home.step1.title': 'تحليل سؤالك',
  'home.step1.desc': 'نحلل استفسارك البحثي إلى احتياجات معلوماتية محددة',
  'home.step2.title': 'تقييم تغطية المصادر',
  'home.step2.desc': 'نتحقق من القدرات والموصلات التي يمكنها تلبية كل احتياج',
  'home.step3.title': 'بناء مسار التحقيق',
  'home.step3.desc': 'نؤلف قالباً يوجه جمع الأدلة والتحليل',

  'home.composing': 'نؤلف قالب التحقيق الخاص بك...',
  'home.composing.sub': 'كشف الاحتياجات · مطابقة القدرات · التحقق من التغطية',
  'home.investigationId': 'معرّف التحقيق',
  'home.moldId': 'قالب الوصفة',
  'home.detectedNeeds': 'الاحتياجات البحثية المكتشفة',
  'home.coverage': 'تغطية المصادر',
  'home.gaps': 'فجوات التغطية',
  'home.complete': 'مكتمل',
  'home.partial': 'تغطية جزئية',
  'home.blocker': 'تقرير عائق التغطية',
  'home.blocker.title': 'لا يمكن التحقيق الكامل في هذا السؤال بعد',
  'home.blocker.desc':
    'ترفض منارة اختلاق الأدلة. بعض الاحتياجات المعلوماتية لا تملك موصلاً تشغيلياً — نُرجع تقرير عائق تغطية منظّماً بدلاً من مُخرَج بحثي.',
  'home.workspaceNotice': 'مساحة التحقيق الكاملة مجدولة لمرحلة التنفيذ التالية.',
  'home.newDomain': 'نطاق جديد',
  'home.newDomainHint': 'لا يوجد قالب مطابق لهذا الاستفسار — تم توليد قالب نطاق جديد.',
  'home.fixtureBadge': 'بيانات تطوير تجريبية',
  'home.fixtureHint': 'تعذّر الوصول إلى الخادم على المنفذ 8000 — هذا التركيب بيانات تجريبية للمراجعة البصرية.',
  'home.deliverable.research_deliverable': 'مُخرَج بحثي',
  'home.deliverable.coverage_blocker_report': 'تقرير عائق التغطية',
  'home.deliverableType': 'نوع المُخرَج',
  'home.selectionReasoning': 'سبب الاختيار',
  'home.foundryResolution': 'قرار المصنع',
  'home.resolutionNotes': 'ملاحظات القرار',
  'home.connectorIds': 'الموصلات',
  'home.capability': 'القدرة',
  'home.relevance': 'الصلة',
  'home.need': 'الاحتياج',
  'home.catalogComplete': 'الكتالوج مكتمل',
  'home.catalogComplete.yes': 'نعم — كل احتياج لديه بطاقة في الكتالوج على الأقل',
  'home.catalogComplete.no': 'لا — بعض الاحتياجات غير معروفة في الكتالوج',
  'home.composedAt': 'تاريخ التركيب',
  'home.detectionReasoning': 'سبب الكشف',
  'home.compositionNotes': 'ملاحظات التركيب',
  'home.startNew': 'بدء تحقيق جديد',

  'nav.home': 'الرئيسية',
  'nav.workspace': 'مساحة التحقيق',
  'nav.memory': 'مستكشف الذاكرة',
  'nav.registry': 'سجل القدرات',
  'nav.foundry': 'مصنع المصادر',
  'nav.molds': 'مصنع القوالب',
  'nav.agents': 'سجل الوكلاء',
  'nav.foresight': 'التنبؤ',
  'nav.publishing': 'استوديو النشر',
  'nav.comingLater': 'قريباً',
  'nav.active': 'نشط',
  'nav.section.intelligence': 'الذكاء',
  'nav.section.factory': 'المصنع',
  'nav.section.studio': 'الاستوديو',

  'demo.mode': 'وضع العرض أحادي المستأجر',
  'demo.version': 'الإصدار 0.1 · معاينة الواجهة',

  'status.online': 'متصل',
  'status.offline': 'غير متصل (بيانات تجريبية)',
  'status.checking': 'جارٍ الفحص…',

  'error.title': 'حدث خطأ ما',
  'error.retry': 'إعادة المحاولة',
  'error.compose': 'تعذّر تركيب قالب التحقيق.',
  'error.status': 'تعذّر الوصول إلى خدمة منارة.',

  'header.menu': 'القائمة',
  'header.closeMenu': 'إغلاق القائمة',
  'header.collapseSidebar': 'طي الشريط الجانبي',
  'header.expandSidebar': 'توسيع الشريط الجانبي',
  'header.language': 'اللغة',
  'header.languageEn': 'English',
  'header.languageAr': 'العربية',
};

const dictionaries: Record<Language, Dict> = { en, ar };

interface LanguageContextValue {
  lang: Language;
  dir: 'ltr' | 'rtl';
  setLang: (l: Language) => void;
  toggleLang: () => void;
  t: (key: string, vars?: Record<string, string>) => string;
}

const LanguageContext = React.createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = React.useState<Language>('en');

  React.useEffect(() => {
    const html = document.documentElement;
    html.lang = lang;
    html.dir = lang === 'ar' ? 'rtl' : 'ltr';
  }, [lang]);

  const setLang = React.useCallback((l: Language) => setLangState(l), []);
  const toggleLang = React.useCallback(
    () => setLangState((p) => (p === 'en' ? 'ar' : 'en')),
    [],
  );

  const t = React.useCallback(
    (key: string, vars?: Record<string, string>) => {
      const dict = dictionaries[lang] ?? en;
      let value = dict[key] ?? en[key] ?? key;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) {
          value = value.replace(new RegExp(`\\{\\{${k}\\}\\}`, 'g'), v);
        }
      }
      return value;
    },
    [lang],
  );

  const value: LanguageContextValue = {
    lang,
    dir: lang === 'ar' ? 'rtl' : 'ltr',
    setLang,
    toggleLang,
    t,
  };

  return (
    <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = React.useContext(LanguageContext);
  if (!ctx) {
    throw new Error('useLanguage must be used inside <LanguageProvider>');
  }
  return ctx;
}
