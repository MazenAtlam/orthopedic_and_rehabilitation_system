# Local orthopedic ICD-10 catalog

Download the English 2019 metadata release from the [WHO ICD-10 download page](https://icdcdn.who.int/icd10/index.html). Use the archive named `icd102019enMeta.zip` and keep it on the local machine. From the `backend` directory with the project environment and database configured:

```powershell
python -m alembic upgrade head
python -m flask --app wsgi load-icd10 --archive 'C:\path\icd102019enMeta.zip'
```

The importer checks the release checksum and loads 679 terminal codes from chapter M and the fracture and dislocation categories S12/S13 through S92/S93. It preserves the WHO code and title and imports in one transaction. Repeat imports update those entries and preserve other codes and their references. The four fictional-demo lookup entries remain available to tests that run without the archive. Search as staff at `GET /api/v1/icd10?q=M16.1`.

[WHO guidance on ICD-10 licensing](https://cdn.who.int/media/docs/default-source/publishing-policies/copyright/who-faq-licensing-icd-10.pdf).
