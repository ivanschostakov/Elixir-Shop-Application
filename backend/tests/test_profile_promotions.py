from types import SimpleNamespace

from src.app.modules.users.me.promotions import _representative_product


def _link(*, product_id: int, archived: bool, has_image: bool, in_stock: bool, priority: int):
    return SimpleNamespace(
        product=SimpleNamespace(
            id=product_id,
            archived=archived,
            has_image=has_image,
            in_stock=in_stock,
            priority=priority,
        )
    )


def test_category_promotion_prefers_an_active_product_with_a_photo():
    category = SimpleNamespace(
        products_by_category=[
            _link(product_id=1, archived=False, has_image=False, in_stock=True, priority=100),
            _link(product_id=2, archived=True, has_image=True, in_stock=True, priority=200),
            _link(product_id=3, archived=False, has_image=True, in_stock=False, priority=5),
        ]
    )

    representative = _representative_product(category)

    assert representative is not None
    assert representative.id == 3
