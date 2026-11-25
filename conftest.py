"""공통 pytest 설정 (A 소유, TEAM_CONTRACT §3.4).

이 파일이 저장소 루트에 있으면 pytest가 루트를 import 경로에 넣어 주므로,
테스트에서 `from src... import ...`, `from sample_data... import ...`를 쓸 수 있다.

공용 fixture
- samples: 코드로 만든 샘플 영상 dict
- fake_db: Firebase 키 없이 쓰는 메모리 가짜 Firestore (get_db()를 바꿔 끼움)
- local_storage: 임시 폴더를 영상 저장소(STORAGE_DIR)로 쓰게 함
"""

import copy

import pytest

from sample_data.generate_samples import make_samples


@pytest.fixture(scope="session")
def samples() -> dict:
    """코드로 만든 샘플 영상 dict (PNG 파일을 읽지 않음). 예: samples["normal"]."""
    return make_samples(seed=0)


# ---------------------------------------------------------------------------
# 메모리 가짜 Firestore — 실제 google.cloud.firestore 사용법 중 우리가 쓰는 부분만 흉내 낸다.
#   db.collection("cases").document(id).set(dict) / .get() / .update(dict)
#   db.collection("images").where(filter=FieldFilter("case_id", "==", x)).stream()
#   batch = db.batch(); batch.set(ref, dict); batch.commit()
# 저장된 값은 fake_db.data["cases"]["case_..."]처럼 직접 들여다볼 수 있다.
# 필요한 기능(order_by, transaction 등)이 더 있으면 A에게 요청한다.
# ---------------------------------------------------------------------------

class FakeSnapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return copy.deepcopy(self._data) if self._data is not None else None


class FakeDocument:
    def __init__(self, db, collection, doc_id):
        self._db, self._collection, self.id = db, collection, doc_id

    def _docs(self):
        return self._db.data.setdefault(self._collection, {})

    def get(self):
        return FakeSnapshot(self.id, self._docs().get(self.id))

    def set(self, data):
        self._docs()[self.id] = copy.deepcopy(dict(data))

    def update(self, data):
        if self.id not in self._docs():
            raise KeyError(f"{self._collection}/{self.id} 문서가 없습니다")
        self._docs()[self.id].update(copy.deepcopy(dict(data)))


class FakeQuery:
    def __init__(self, db, collection, filters=()):
        self._db, self._collection, self._filters = db, collection, list(filters)

    def where(self, field_path=None, op_string=None, value=None, *, filter=None):
        if filter is not None:
            field_path, op_string, value = filter.field_path, filter.op_string, filter.value
        if op_string != "==":
            raise NotImplementedError("가짜 Firestore는 '==' 조건만 지원합니다")
        return FakeQuery(self._db, self._collection, [*self._filters, (field_path, value)])

    def stream(self):
        for doc_id, data in list(self._db.data.get(self._collection, {}).items()):
            if all(data.get(field) == value for field, value in self._filters):
                yield FakeSnapshot(doc_id, data)


class FakeCollection(FakeQuery):
    def document(self, doc_id):
        return FakeDocument(self._db, self._collection, doc_id)


class FakeBatch:
    def __init__(self, db):
        self._db, self._ops = db, []

    def set(self, ref, data):
        self._ops.append(("set", ref, data))

    def update(self, ref, data):
        self._ops.append(("update", ref, data))

    def commit(self):
        if self._db.fail_commit:
            raise RuntimeError("가짜 Firestore: 커밋 실패 (테스트용)")
        for op, ref, data in self._ops:  # 실제 batch처럼 전부 적용하거나 하나도 적용하지 않는다
            getattr(ref, op)(data)


class FakeFirestore:
    def __init__(self):
        self.data: dict[str, dict[str, dict]] = {}
        self.fail_commit = False  # True로 바꾸면 batch.commit()이 실패한다

    def collection(self, name):
        return FakeCollection(self, name)

    def batch(self):
        return FakeBatch(self)


@pytest.fixture
def fake_db(monkeypatch):
    """get_db()가 메모리 가짜 Firestore를 돌려주게 한다. 개발 모드는 끈다."""
    db = FakeFirestore()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr("src.services.firebase_client.get_db", lambda: db)
    return db


@pytest.fixture
def local_storage(tmp_path, monkeypatch):
    """영상 저장소를 테스트마다 새 임시 폴더로 바꾼다. 반환: 그 폴더 경로."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    return tmp_path
