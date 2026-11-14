import pytest

from src.database.product_text import normalize_product_text
from src.database.schemas.catalog.product import ProductCreate


FAQ = "(function () { var items = document.querySelectorAll('details'); items.forEach(function (details) { details.open = false; }); })();"


@pytest.mark.parametrize("fragment", [
    "<script>alert(1);</script>", "<style>p { color: red; }</style>",
    "&lt;script type=&quot;text/javascript&quot;&gt;alert(1)&lt;/script&gt;",
    "<template>Hidden fragment</template>", FAQ,
])
def test_product_text_removes_scripts_without_losing_visible_markup(fragment):
    expected = "<h3>FAQ</h3><details><summary>Question</summary><p>Answer &amp; details</p></details>"
    assert normalize_product_text(expected + fragment) == expected


def test_cleanup_applies_to_all_product_content_fields():
    product = ProductCreate(sku="test", name="Test", description=FAQ, usage=f"<p>Usage</p>{FAQ}",
                            expiration="<p>Details</p><script>incomplete script")
    assert product.description is None
    assert product.usage == "<p>Usage</p>"
    assert product.expiration == "<p>Details</p>"
