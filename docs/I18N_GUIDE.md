# Internationalization (i18n) Guide

## Overview

Time Tracker uses **react-i18next** for internationalization. All user-facing strings are extracted into JSON translation files, making it easy to add new languages.

## Architecture

```
frontend/src/i18n/
├── config.ts                    # i18next initialization
└── locales/
    └── en/
        └── translation.json     # English translations (source of truth)
```

## Adding Translations to a Component

### 1. Import the hook

```tsx
import { useTranslation } from 'react-i18next';
```

### 2. Use in your component

```tsx
function MyComponent() {
  const { t } = useTranslation();

  return (
    <div>
      <h1>{t('myNamespace.title')}</h1>
      <p>{t('myNamespace.description')}</p>
    </div>
  );
}
```

### 3. With interpolation

```tsx
// In translation.json:
// "welcome": "Hello, {{name}}!"

<p>{t('login.signInTo', { appName: 'Time Tracker' })}</p>
```

### 4. With react-hook-form

```tsx
const { register } = useForm();

<Input
  label={t('login.emailLabel')}
  {...register('email', {
    required: t('login.emailRequired'),
    pattern: {
      value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
      message: t('login.emailInvalid'),
    },
  })}
/>
```

## Translation Key Conventions

### Namespace Structure

| Namespace    | Purpose                          |
|-------------|----------------------------------|
| `common`    | Shared strings (Save, Cancel…)   |
| `nav`       | Sidebar navigation labels        |
| `login`     | Login page                       |
| `dashboard` | Dashboard page                   |
| `time`      | Time tracking page               |
| `projects`  | Projects page                    |
| `teams`     | Teams page                       |
| `tasks`     | Tasks page                       |
| `settings`  | Settings page                    |
| `admin`     | Admin/user management            |
| `staff`     | Staff management                 |
| `timer`     | Timer widget                     |
| `notFound`  | 404 page                         |
| `connection`| WebSocket connection status      |

### Key Naming Rules

- Use **camelCase** for keys: `loginFailed`, not `login_failed`
- Use descriptive names: `emailRequired`, not `err1`
- Group related strings: `login.emailLabel`, `login.emailRequired`
- Suffix patterns:
  - `*Label` → form field labels
  - `*Placeholder` → input placeholders
  - `*Required` → validation messages
  - `*Msg` → notification body text
  - `*Title` → section/page titles
  - `*Subtitle` → section descriptions
  - `*Confirm` → confirmation dialog text

## Adding a New Language

1. Create the locale folder:
   ```
   frontend/src/i18n/locales/es/translation.json
   ```

2. Copy the English file and translate all values:
   ```json
   {
     "login": {
       "welcomeBack": "Bienvenido de nuevo",
       "signIn": "Iniciar sesión"
     }
   }
   ```

3. Register in `config.ts`:
   ```ts
   import es from './locales/es/translation.json';

   const resources = {
     en: { translation: en },
     es: { translation: es },
   };
   ```

4. Add a language switcher component (future phase).

## Testing

The i18n test suite at `src/test/i18n.test.ts` validates:

- All required namespaces exist
- Key pages have complete translation coverage
- No empty string values
- Correct interpolation syntax (`{{variable}}`)
- Minimum key count threshold

Run tests:
```bash
cd frontend && npx vitest run src/test/i18n.test.ts
```

## Pages with i18n Extraction (Phase 9A)

| Page / Component              | Status  |
|-------------------------------|---------|
| LoginPage                     | ✅ Done |
| DashboardPage                 | ✅ Done |
| TimePage                      | ✅ Done |
| NotFoundPage                  | ✅ Done |
| Sidebar                       | ✅ Done |
| ConnectionStatusIndicator     | ✅ Done |
| ProjectsPage                  | 🔲 Phase 9B |
| TeamsPage                     | 🔲 Phase 9B |
| TasksPage                     | 🔲 Phase 9B |
| SettingsPage                  | 🔲 Phase 9B |
| AdminPage                     | 🔲 Phase 9B |
| StaffPage                     | 🔲 Phase 9B |
| TimerWidget                   | 🔲 Phase 9B |

## Troubleshooting

### Missing translation shows key path
If you see raw key paths like `login.welcomeBack` in the UI, check:
1. The key exists in `translation.json`
2. `i18n/config.ts` is imported in `main.tsx`
3. The component uses `useTranslation()` hook

### Tests fail after adding new keys
Update `src/test/i18n.test.ts` to include the new keys in the appropriate test.
