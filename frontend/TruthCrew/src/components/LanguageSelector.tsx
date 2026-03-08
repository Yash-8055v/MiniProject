interface LanguageSelectorProps {
  selected: 'en' | 'hi' | 'mr';
  onChange: (lang: 'en' | 'hi' | 'mr') => void;
}

const LanguageSelector = ({ selected, onChange }: LanguageSelectorProps) => {
  const languages = [
    { code: 'en' as const, label: 'English' },
    { code: 'hi' as const, label: 'हिंदी' },
    { code: 'mr' as const, label: 'मराठी' },
  ];

  return (
    <div className="flex items-center gap-2">
      {languages.map((lang) => (
        <button
          key={lang.code}
          onClick={() => onChange(lang.code)}
          className={`language-btn ${selected === lang.code ? 'language-btn-active' : ''}`}
        >
          {lang.label}
        </button>
      ))}
    </div>
  );
};

export default LanguageSelector;
