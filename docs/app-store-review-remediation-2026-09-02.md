# App Store review remediation — September 2, 2026

Submission: `088c2eb7-4fe4-45e6-82c9-1fe813302d0a`  
Reviewed version: `1.0 (34)`  
Review devices: iPad Air 11-inch (M3), iPhone 17 Pro Max

Status updated September 7, 2026: the permanent iOS account-and-support scope was
implemented and published to build 34 through the production OTA channel for runtime
`0.1.1` (update group `b5f3acaf-3787-4925-8d38-99b9bbea2963`). Replacement iPhone
and iPad screenshots were uploaded to App Store Connect. The description, keywords,
promotional text, review notes, and corrected age-rating answers are prepared but
must still be saved. The remaining external blocker is Apple's organization-account
requirement under 5.1.1(ix).

The public website document inspection below sampled GHK-Cu and RetaSlim rather than
auditing the full catalog.

## Website documentation checked on September 2, 2026

The [certificates page](https://elixirpeptide.com/certificates/) has three scanned
pages: one voluntary conformity certificate and two product-list appendices.
The certificate tabs on the
[GHK-Cu page](https://elixirpeptide.com/catalog/kosmeticheskie_peptidy_kozha_volosy_zagar/ghk_cu/)
and [RetaSlim page](https://elixirpeptide.com/catalog/snizhenie_vesa_i_zhiroszhigateli/retaslim/retaslim_5mg/)
also expose downloadable PDFs. Six distinct PDFs, 15 pages in total, were downloaded
and visually inspected. The files are image scans, without extractable PDF text.

**Finding:** the reviewed documents contain voluntary conformity and laboratory
test evidence. None of these documents establishes a medicinal-product marketing
authorization, approved therapeutic indication, or clearance for the app's medical
advice/dosing functionality. This conclusion is limited to the documents inspected;
it does not establish that other approvals do not exist.

| Document | What the document actually states | Original source |
| --- | --- | --- |
| Voluntary conformity certificate, 3 pages | No. РОСС RU.МЛ10.Н00102, form 0013648; stated term March 17, 2025–March 16, 2028. Issued to ООО «СЛИМЭЛИКСИРПЕПТАЙД». Two appendices contain 46 numbered entries, including Retatrutide, BPC-157, TB-500 and GHK-Cu. The footer says it does not apply to mandatory certification. | [Certificate and appendices](https://elixirpeptide.com/upload/iblock/b7e/p69bfe70f4fq5zmmexzh3t6z9we95ppw.pdf) |
| GHK-Cu certificate of analysis, 1 page | Batch 2604130092; report April 14, 2026; HPLC purity reported as 99.57%. The conclusion is conformity to an in-house standard. | [GHK-Cu analysis](https://elixirpeptide.com/upload/iblock/ba5/wjqejshznsmbw39qs9czdgcibrnw7dv0.pdf) |
| GHK-Cu peptide passport, 3 pages | Date printed as 10/06/2026; HPLC purity reported as 99.29%, plus chromatography and mass-spectrometry results. | [GHK-Cu passport](https://elixirpeptide.com/upload/iblock/e49/608xp9crq2q9con327rroidtbs3d87xq.pdf) |
| Janoshik Retatrutide test report, 2 pages | Task 65982, analysis May 26, 2025; sample labelled Retatrutide 10 mg, measured content 10.27 mg and purity 99.423%; includes sample photo. This describes a tested sample. | [Janoshik report](https://elixirpeptide.com/upload/iblock/eea/z9g88r9tsc3x8gp3cmc1jk4v7f1wq18o.pdf) |
| Retatrutide certificate of analysis, 3 pages | January 18, 2026; HPLC purity reported as 99.57%, with analytical traces. Explicitly labels the product for research use only. | [Retatrutide analysis](https://elixirpeptide.com/upload/iblock/012/xv2333k5ai5i3mpru8nx7vveah3o2dww.pdf) |
| Retatrutide peptide passport, 3 pages | January 27, 2026; HPLC purity reported as 99.66%, with chromatography and mass-spectrometry results. | [Retatrutide passport](https://elixirpeptide.com/upload/iblock/0a9/h3geh512rq7kzus9bzvt3walp4u65cek.pdf) |

Unmodified local copies are stored in `output/pdf/elixir-documentation-2026-09-02/`.
The reported laboratory results and certificate status have not been independently
authenticated with the issuers. Results from different reports must not be treated
as evidence for every current product variant or batch.

### Standards cited by the conformity certificate need clarification

The certificate cites ГОСТ Р 53974-2010 and prints ГОСТ Р 34353-2017.
Rosstandart identifies
[ГОСТ Р 53974-2010](https://protect.gost.ru/gost/details/b1a336ab-5565-4b6a-a992-0eb4e792a9ed)
as a food-industry enzyme test method and lists it as withdrawn. Its
[withdrawal record](https://protect.gost.ru/gost/changesdetails/e754af29-6a1d-4d14-b388-d90a528301ab)
gives July 1, 2019 as the replacement date. The official entry for
[ГОСТ 34353-2017](https://protect.gost.ru/gost/details/9bf8b1ed-cdc8-4d3f-aae4-63ce93c82de2)
(without the extra Р) concerns dry animal-origin milk-clotting enzymes for dairy
production. Those scopes do not demonstrate approval of therapeutic peptide use.
Ask the issuer to explain the applicability, designation and use of the withdrawn
standard before presenting the certificate as regulatory evidence. This observation
does not determine whether the certificate itself is authentic or legally valid.

### The manufacturer and storefront list different legal entities

The certificate names ООО «СЛИМЭЛИКСИРПЕПТАЙД» as manufacturer and certificate
holder (ОГРН 1250200006198; ИНН 0278986386). However, the site's
[legal-details page](https://elixirpeptide.com/about/requisites/)
lists ИП Хакимов Руслан Ралифович as the business. This could be a legitimate
manufacturer/retailer relationship, but that relationship was not established by
the inspected documents.

Apple's [enrollment requirements](https://developer.apple.com/programs/enroll/)
place sole proprietors under individual enrollment and require a legal entity for
organization enrollment. Verify whether the LLC is the entity that actually
provides the app's services and can enroll or hold the appropriate Apple membership.
Its appearance on a product certificate does not by itself resolve 5.1.1(ix).

### Website wording does not resolve the medical objection

The site footer limits materials to research use, while the inspected GHK-Cu page
contains healing/health claims, physician-supervised use language and purchase
controls. The [About page](https://elixirpeptide.com/about/) asserts that registration
documents are available, but the documents inspected above do not include such a
marketing authorization. Request the actual authorization documents and public
registry references if the business has them.

The [public offer](https://elixirpeptide.com/privacy/offer/) also contains unresolved
company/address placeholders and references the `.ru` domain. Correct the legal
identity consistently before using these pages as supporting submission material.

**Next evidence to obtain:** the relevant regulator's approval/registration number,
official registry entry, authorized product/form/manufacturer and indications for
each retained regulated offering; any documentation covering the app's retained
medical functionality; and confirmation of the service-providing legal entity.
Quality reports can supplement that evidence but should not be described as those
approvals in the App Review response.

## What prevents resubmission

The rejection concerns the actual product offering as well as presentation. Removing
Apple imagery and adding a medical disclaimer would leave the organization-account
and product-safety objections unresolved.

| Guideline | Required action from the rejection | Where it must be completed |
| --- | --- | --- |
| 5.1.1(ix) | Submit through an organization account belonging to the entity providing the service. A publishing-permission letter does not resolve this objection. | Apple Developer membership; account holder |
| 5.2.5 | Replace screenshots containing Apple logo imagery or confusing Apple branding. | App Store Connect, all affected devices and localizations |
| 1.4.5 | Remove the harmful functionality Apple identified, including promotion and sale of the flagged investigational or non-approved compounds for apparent human use. | Catalog, app, backend, promotional content, AI and linked purchase paths |
| 1.4.1 | Supply the requested applicable regulatory documentation for retained medical functionality, and include the doctor-advice reminder in the description. If documentation is unavailable, propose removing the medical functionality and ask Apple to assess the revised scope. | Product decision, supporting documents, app/backend and store description |
| 2.1(a) | Replace screenshots containing review-process references and ensure the release content is final. | App Store Connect and the content shown by the app |

These requirements are taken from the supplied rejection. Apple's published
[App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
provide the broader review framework. No change here guarantees approval.

## Confirmed repository findings

### AI currently connects medical advice with purchasing

- `backend/src/app/services/ai/chat.py:78`: `_build_commerce_ai_input` tells the
  assistant to use medical and physiological knowledge to choose peptides. It
  explicitly requests catalog recommendations for weight-loss questions, then
  supplies product cards and basket actions.
- `backend/src/integrations/ai/instructions/free.txt:93`: the assistant is assigned
  the role of a professor of medicine. The following instructions require promotion
  of specific peptide purchase links; later content requests application and dosage
  information.
- `backend/src/integrations/ai/instructions/premium.txt:93`: the premium assistant
  also claims medical expertise; line 113 requests indications, dosages, course
  duration, side effects, and compatibility. The instructions discourage saying
  that the assistant is not a doctor.
- `backend/src/integrations/ai/client.py:41` loads these instruction files, and
  `backend/src/app/services/ai/chat.py:299` passes the commerce prompt to the client.
  These are connected code paths, not merely unused marketing copy.

Changing only the commerce prompt would leave conflicting instructions in the
free and premium files. A disclaimer alone would not remove the underlying behavior.

### The local screenshot still presents medical product positioning

The inspected file is
`frontend/assets/store/screenshots/correct-phone-layout-1242x2688.jpg`.
It shows a GHK-Cu promotion, peptide vials with prices, and categories including
anti-age therapy, antidepressants, and immune-system products. Although some
packaging says “Research Use Only,” the overall presentation still includes human
health positioning. This is a review-risk observation, not a determination of any
specific product's regulatory status.

No obvious Apple logo or review-process message was visible in this local image.

The App Store Connect Media Manager was inspected on September 7, 2026. The exact
asset that caused both 5.2.5 and the review-process portion of 2.1(a) is the first
iPad 13-inch screenshot:
`Simulator Screenshot - iPad Pro 13-inch (M5) - 2026-05-15 at 02.58.19.png`.
It contains a large Apple logo and the text “HELLO APPLE TESTING TEAM!” followed
by a thank-you message to the reviewer. Delete this uploaded screenshot.

Two additional uploaded screenshots show unfinished placeholder content and should
also be replaced before resubmission:

- iPad: `Simulator Screenshot - iPad Pro 13-inch (M5) - 2026-05-15 at 02.58.28.png`
- iPhone: `screenshot_07_1242x2688.png`

Both display an “Articles coming soon” state and say that the tab is reserved for
future editorial content. The remaining four iPhone and five iPad screenshots did
not contain Apple branding or App Review messages during this inspection.

### One review banner is already filtered locally

`frontend/screens/home/home-screen.tsx:179` excludes image paths containing
`apple-testing-team-banner`; the filter is applied at line 290. This does not prove
the deployed build contains the filter, remove the source banner, or change images
already uploaded to App Store Connect. Check the live banner source as well.

## Product decision needed before changing functionality

Determine whether there are applicable regulatory documents covering the exact
products, claimed uses, medical functionality, seller and intended territories.
An ingredient name, research label, laboratory purity report, or general company
certificate does not by itself establish approval for the submitted offering.

If appropriate documentation exists, map each document to the retained product or
feature and territory, and attach it for Apple's assessment. The 1.4.5 objection
still requires a response about the specifically flagged functionality.

If it does not exist, the proposed release scope is a store limited to products
whose sale and presentation can be substantiated, with shopping and order support
in place of medical advice. Implement that scope consistently:

1. Identify the exact excluded product and variant IDs and review the remaining
   catalog. Do not infer that every peptide has the same status.
2. Enforce product eligibility in catalog/search, direct product links, similar
   products, recommendations, favorites, AI tools, basket additions, saved drafts,
   reorder flows and final checkout. Revalidate existing baskets and drafts.
3. Ensure catalog imports/sync cannot restore excluded items; invalidate affected
   caches. A frontend-only filter is insufficient.
4. Remove unsupported therapeutic positioning from categories, banners, product
   descriptions, articles, promotional notifications and purchase links. Review
   community content and support workflows for the same issue.
5. Replace both AI instruction files and the commerce prompt. Remove medical
   personas, personalized treatment selection, dosing/course instructions and
   static links to excluded products. Limit supported assistance to the permitted
   catalog and ordinary order support, and refer medical decisions to a clinician.
6. Verify actual AI responses and tool actions, including attachments, follow-up
   questions and existing conversations. Prompt wording alone is not proof of
   reliable restrictions.
7. Describe the changed scope in review notes and apply it to ordinary users as
   well as reviewers. Do not use reviewer-specific hiding or restore rejected
   functionality after review.

The catalog and AI changes affect the service's core offering and shared backend.
The product list, documentation and intended platform scope are needed before
implementing them accurately.

## Account and metadata work

The account holder can request an individual-to-organization conversion. Apple's
[membership instructions](https://developer.apple.com/help/account/membership/updating-your-account-information/)
say the requester must be a founder/cofounder and provide information including
the organization's D-U-N-S Number; business verification may be required.

Do not assume creating a second account makes this app transferable. Apple's
[transfer criteria](https://developer.apple.com/help/app-store-connect/transfer-an-app/app-transfer-criteria/)
require at least one version already released to the App Store. If version 1.0
has never been released, ask Developer Support about conversion or the appropriate
new-account submission path before changing bundle identifiers or signing.

For screenshots, open the selected version's **App Preview and Screenshots → View
All Sizes in Media Manager**, then inspect each device size and localization.
[Apple's removal instructions](https://developer.apple.com/help/app-store-connect/manage-app-information/remove-app-previews-or-screenshots/)
explain the controls and editable-status requirement. Capture replacements from
the final app with the final catalog and fictional customer data. Remove Apple
logo imagery, review-team greetings and review-process text. Keep reviewer access
instructions in App Review Information.

Suggested description reminder, to accompany the resolved medical scope:

> Seek a doctor's advice in addition to using this app and before making any
> medical decisions.

Russian localization:

> Помимо использования приложения, обращайтесь за советом к врачу перед принятием
> любых медицинских решений.

This reminder is an additional requirement, not a replacement for removing the
flagged functionality or providing the requested documentation.

## Draft clarification message — not sent

Hello App Review,

Thank you for the detailed feedback on submission
088c2eb7-4fe4-45e6-82c9-1fe813302d0a, version 1.0 (34). We understand that the
organization-account, medical-functionality, product-safety and screenshot issues
must each be addressed.

Could you identify representative product names and screen paths that triggered
Guidelines 1.4.5 and 1.4.1, and the affected screenshot device sizes and localizations
for Guidelines 5.2.5 and 2.1(a)? This will help us verify that the revised submission
addresses every reported issue.

Thank you.

## Evidence required before resubmitting

- Organization enrollment verified for the submitting account.
- Retained products/features and relevant documentation resolved; removed
  functionality inaccessible through direct links and purchase paths.
- Revised app and backend tested on iPhone and iPad, including AI behavior and
  existing carts/drafts.
- Final screenshots replaced in every affected device/localization slot, and
  localized descriptions updated.
- Review notes describe changes actually completed and include working reviewer
  access. Documentation is attached where applicable.

`frontend/eas.json` uses remote app versioning. Verify the uploaded version/build
in EAS and App Store Connect rather than treating the local `app.json` build
number as evidence of the submitted version.
