import uuid

from conftest import make_blank_pdf_bytes, make_docx_bytes

from auth import encode_access_token

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_CONTENT_TYPE = "application/pdf"


def user_headers(tenant_id: uuid.UUID, employee_id: uuid.UUID | None = None) -> dict:
    token = encode_access_token(tenant_id, employee_id or uuid.uuid4())
    return {"Authorization": f"Bearer {token}"}


async def upload(
    client, headers, *, scope, department=None, content=None, filename="doc.docx",
    content_type=DOCX_CONTENT_TYPE,
):
    content = content or make_docx_bytes(["some default content about async work"])
    data = {"scope": scope}
    if department is not None:
        data["department"] = department
    files = {"file": (filename, content, content_type)}
    return await client.post("/documents", data=data, files=files, headers=headers)


async def test_missing_authorization_header_is_401(client):
    resp = await client.get("/documents")
    assert resp.status_code == 401


async def test_upload_company_scoped_document(client):
    tenant_id = uuid.uuid4()
    resp = await upload(
        client, user_headers(tenant_id), scope="company",
        content=make_docx_bytes(["Our company holiday policy is generous."]),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["scope"] == "company"
    assert body["status"] == "ready"
    assert body["department"] is None
    assert body["employee_id"] is None


async def test_upload_department_scope_requires_department(client):
    tenant_id = uuid.uuid4()
    resp = await upload(client, user_headers(tenant_id), scope="department")
    assert resp.status_code == 400


async def test_upload_department_scoped_document(client):
    tenant_id = uuid.uuid4()
    resp = await upload(
        client, user_headers(tenant_id), scope="department", department="Engineering",
        content=make_docx_bytes(["Engineering on-call rotation is weekly."]),
    )
    assert resp.status_code == 201
    assert resp.json()["department"] == "Engineering"


async def test_upload_personal_scope_uses_callers_own_employee_id(client):
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    resp = await upload(
        client, user_headers(tenant_id, employee_id), scope="personal",
        content=make_docx_bytes(["My personal notes on the Q3 roadmap."]),
    )
    assert resp.status_code == 201
    assert resp.json()["employee_id"] == str(employee_id)


async def test_upload_empty_document_fails_and_marks_document_failed(client):
    tenant_id = uuid.uuid4()
    resp = await upload(
        client, user_headers(tenant_id), scope="company",
        content=make_blank_pdf_bytes(), filename="blank.pdf", content_type=PDF_CONTENT_TYPE,
    )
    assert resp.status_code == 422

    resp = await client.get("/documents", headers=user_headers(tenant_id))
    docs = resp.json()
    assert len(docs) == 1
    assert docs[0]["status"] == "failed"


async def test_delete_document(client):
    tenant_id = uuid.uuid4()
    headers = user_headers(tenant_id)
    resp = await upload(client, headers, scope="company")
    document_id = resp.json()["id"]

    resp = await client.delete(f"/documents/{document_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.delete(f"/documents/{document_id}", headers=headers)
    assert resp.status_code == 404


async def test_documents_isolated_across_tenants(client):
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    await upload(client, user_headers(tenant_a), scope="company")

    resp = await client.get("/documents", headers=user_headers(tenant_b))
    assert resp.json() == []

    resp = await client.get("/documents", headers=user_headers(tenant_a))
    assert len(resp.json()) == 1


async def test_search_returns_company_scoped_chunks_to_anyone_in_tenant(client):
    tenant_id = uuid.uuid4()
    await upload(
        client, user_headers(tenant_id), scope="company",
        content=make_docx_bytes(["The company holiday policy allows unlimited PTO."]),
    )

    resp = await client.post(
        "/search", json={"query": "holiday policy PTO"}, headers=user_headers(tenant_id)
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert "holiday" in results[0]["content"]
    assert results[0]["scope"] == "company"


async def test_search_department_scope_requires_matching_department(client):
    tenant_id = uuid.uuid4()
    await upload(
        client, user_headers(tenant_id), scope="department", department="Engineering",
        content=make_docx_bytes(["Engineering deploys happen every Tuesday."]),
    )

    # searching without specifying the department: no access to it
    resp = await client.post(
        "/search", json={"query": "deploys Tuesday"}, headers=user_headers(tenant_id)
    )
    assert resp.json() == []

    # searching as a member of a different department: still no access
    resp = await client.post(
        "/search",
        json={"query": "deploys Tuesday", "department": "Sales"},
        headers=user_headers(tenant_id),
    )
    assert resp.json() == []

    # searching with the matching department: found
    resp = await client.post(
        "/search",
        json={"query": "deploys Tuesday", "department": "Engineering"},
        headers=user_headers(tenant_id),
    )
    results = resp.json()
    assert len(results) == 1
    assert results[0]["scope"] == "department"


async def test_search_personal_scope_requires_matching_employee_id(client):
    tenant_id, owner_id, other_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await upload(
        client, user_headers(tenant_id, owner_id), scope="personal",
        content=make_docx_bytes(["My personal reminder to renew the SSL certificate."]),
    )

    resp = await client.post(
        "/search",
        json={"query": "SSL certificate renewal", "employee_id": str(other_id)},
        headers=user_headers(tenant_id),
    )
    assert resp.json() == []

    resp = await client.post(
        "/search",
        json={"query": "SSL certificate renewal", "employee_id": str(owner_id)},
        headers=user_headers(tenant_id),
    )
    results = resp.json()
    assert len(results) == 1
    assert results[0]["scope"] == "personal"


async def test_search_combines_all_accessible_scopes(client):
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    await upload(
        client, user_headers(tenant_id), scope="company",
        content=make_docx_bytes(["Company-wide expense policy details."]),
    )
    await upload(
        client, user_headers(tenant_id), scope="department", department="Engineering",
        content=make_docx_bytes(["Engineering expense approval process."]),
    )
    await upload(
        client, user_headers(tenant_id, employee_id), scope="personal",
        content=make_docx_bytes(["My personal expense report notes."]),
    )

    resp = await client.post(
        "/search",
        json={"query": "expense", "department": "Engineering", "employee_id": str(employee_id)},
        headers=user_headers(tenant_id),
    )
    results = resp.json()
    assert {r["scope"] for r in results} == {"company", "department", "personal"}


async def test_search_uses_query_input_type_and_document_uses_document_input_type(client):
    tenant_id = uuid.uuid4()
    await upload(client, user_headers(tenant_id), scope="company")

    await client.post("/search", json={"query": "async work"}, headers=user_headers(tenant_id))

    input_types = [call[1] for call in client.fake_embedder.calls]
    assert "document" in input_types
    assert "query" in input_types
