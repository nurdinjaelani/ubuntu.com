"""
A Flask application for ubuntu.com
"""

# Packages
import os
import talisker.requests
import flask
from canonicalwebteam.flask_base.app import FlaskBase
from canonicalwebteam.templatefinder import TemplateFinder
from canonicalwebteam.search import build_search_view
from canonicalwebteam import image_template
from canonicalwebteam.blog import build_blueprint, BlogViews, BlogAPI
from canonicalwebteam.discourse import (
    DiscourseAPI,
    Docs,
    DocParser,
    EngageParser,
    EngagePages,
)

# Local
from webapp.context import (
    current_year,
    descending_years,
    format_date,
    get_json_feed,
    modify_query,
    month_name,
    months_list,
    get_navigation,
    releases,
)

from webapp.views import (
    accept_renewal,
    advantage_view,
    advantage_shop_view,
    advantage_thanks_view,
    BlogCustomGroup,
    BlogCustomTopic,
    BlogPressCentre,
    BlogSitemapIndex,
    BlogSitemapPage,
    build,
    build_tutorials_index,
    download_harness,
    download_thank_you,
    appliance_install,
    appliance_portfolio,
    ensure_purchase_account,
    get_customer_info,
    get_purchase,
    get_renewal,
    post_advantage_subscriptions,
    post_anonymised_customer_info,
    post_customer_info,
    post_stripe_invoice_id,
    post_renewal_preview,
    post_build,
    releasenotes_redirect,
    search_snaps,
    notify_build,
    build_engage_index,
    engage_thank_you,
    sitemap_index,
)
from webapp.login import login_handler, logout, user_info
from webapp.security.database import db_session
from webapp.security.views import (
    create_notice,
    delete_notice,
    create_release,
    delete_release,
    notice,
    read_notice,
    read_notices,
    notices,
    notices_feed,
    update_notice,
    cve_index,
    cve,
    delete_cve,
    bulk_upsert_cve,
)


CAPTCHA_TESTING_API_KEY = os.getenv(
    "CAPTCHA_TESTING_API_KEY", "6LfYBloUAAAAAINm0KzbEv6TP0boLsTEzpdrB8if"
)

# Set up application
# ===

app = FlaskBase(
    __name__,
    "ubuntu.com",
    template_folder="../templates",
    template_404="404.html",
    template_500="500.html",
    static_folder="../static",
)

# Settings
app.config["CONTRACTS_API_URL"] = os.getenv(
    "CONTRACTS_API_URL", "https://contracts.canonical.com"
).rstrip("/")
app.config["CANONICAL_LOGIN_URL"] = os.getenv(
    "CANONICAL_LOGIN_URL", "https://login.ubuntu.com"
)
session = talisker.requests.get_session()
discourse_api = DiscourseAPI(
    base_url="https://discourse.ubuntu.com/", session=session
)


# Error pages
@app.errorhandler(400)
def bad_request_error(error):
    return flask.render_template("400.html"), 400


@app.errorhandler(410)
def deleted_error(error):
    return flask.render_template("410.html"), 410


# Template context
@app.context_processor
def context():
    return {
        "current_year": current_year,
        "descending_years": descending_years,
        "format_date": format_date,
        "get_json_feed": get_json_feed,
        "modify_query": modify_query,
        "month_name": month_name,
        "months_list": months_list,
        "get_navigation": get_navigation,
        "product": flask.request.args.get("product", ""),
        "request": flask.request,
        "releases": releases(),
        "user_info": user_info(flask.session),
        "utm_campaign": flask.request.args.get("utm_campaign", ""),
        "utm_medium": flask.request.args.get("utm_medium", ""),
        "utm_source": flask.request.args.get("utm_source", ""),
        "CAPTCHA_TESTING_API_KEY": CAPTCHA_TESTING_API_KEY,
        "http_host": flask.request.host,
    }


@app.context_processor
def utility_processor():
    return {"image": image_template}


# Routes
# ===

# Simple routes
app.add_url_rule("/sitemap.xml", view_func=sitemap_index)
app.add_url_rule("/advantage", view_func=advantage_view)
app.add_url_rule("/advantage/subscribe", view_func=advantage_shop_view)
app.add_url_rule(
    "/advantage/subscribe/thank-you", view_func=advantage_thanks_view
)
app.add_url_rule(
    "/advantage/subscribe",
    view_func=post_advantage_subscriptions,
    methods=["POST"],
    defaults={"preview": False},
)
app.add_url_rule(
    "/advantage/subscribe/preview",
    view_func=post_advantage_subscriptions,
    methods=["POST"],
    defaults={"preview": True},
)
app.add_url_rule(
    "/advantage/customer-info", view_func=post_customer_info, methods=["POST"]
)
app.add_url_rule(
    "/advantage/customer-info-anon",
    view_func=post_anonymised_customer_info,
    methods=["POST"],
)
app.add_url_rule(
    "/advantage/<tx_type>/<tx_id>/invoices/<invoice_id>",
    view_func=post_stripe_invoice_id,
    methods=["POST"],
)
app.add_url_rule(
    "/advantage/purchases/<purchase_id>",
    view_func=get_purchase,
    methods=["GET"],
)
app.add_url_rule(
    "/advantage/purchase-account",
    view_func=ensure_purchase_account,
    methods=["POST"],
)
app.add_url_rule(
    "/advantage/renewals/<renewal_id>", view_func=get_renewal, methods=["GET"]
)

app.add_url_rule(
    "/advantage/customer-info/<account_id>",
    view_func=get_customer_info,
    methods=["GET"],
)

app.add_url_rule(
    "/advantage/renewals/<renewal_id>/process-payment",
    view_func=accept_renewal,
    methods=["POST"],
)
app.add_url_rule(
    "/advantage/renewals/<renewal_id>/preview",
    view_func=post_renewal_preview,
    methods=["POST"],
)
app.add_url_rule(
    (
        "/download"
        "/<regex('server|desktop|cloud|raspberry-pi'):category>"
        "/thank-you"
    ),
    view_func=download_thank_you,
)

app.add_url_rule(
    "/download/<regex('server'):category>",
    methods=["GET", "POST"],
    view_func=download_harness,
)

app.add_url_rule("/getubuntu/releasenotes", view_func=releasenotes_redirect)
app.add_url_rule(
    "/search", "search", build_search_view(template_path="search.html")
)
app.add_url_rule(
    "/appliance/<regex('.+'):app>/<regex('.+'):device>",
    view_func=appliance_install,
)
app.add_url_rule(
    "/appliance/portfolio",
    view_func=appliance_portfolio,
)

# blog section

blog_views = BlogViews(
    api=BlogAPI(session=session),
    excluded_tags=[3184, 3265, 3408, 3960],
    per_page=11,
)
app.add_url_rule(
    "/blog/topics/<regex('maas|design|juju|robotics|snapcraft'):slug>",
    view_func=BlogCustomTopic.as_view("blog_topic", blog_views=blog_views),
)
app.add_url_rule(
    "/blog/<regex('cloud-and-server|desktop|internet-of-things'):slug>",
    view_func=BlogCustomGroup.as_view("blog_group", blog_views=blog_views),
)
app.add_url_rule(
    "/blog/press-centre",
    view_func=BlogPressCentre.as_view("press_centre", blog_views=blog_views),
)
app.add_url_rule(
    "/blog/sitemap.xml",
    view_func=BlogSitemapIndex.as_view("sitemap", blog_views=blog_views),
)
app.add_url_rule(
    "/blog/sitemap/<regex('.+'):slug>.xml",
    view_func=BlogSitemapPage.as_view("sitemap_page", blog_views=blog_views),
)
app.register_blueprint(build_blueprint(blog_views), url_prefix="/blog")

# usn section
app.add_url_rule(
    "/security/api/notices/<notice_id>",
    view_func=read_notice,
)
app.add_url_rule(
    "/security/api/notices",
    view_func=read_notices,
)
app.add_url_rule("/security/notices", view_func=notices)
app.add_url_rule(
    "/security/notices", view_func=create_notice, methods=["POST"]
)

app.add_url_rule("/security/notices/<notice_id>", view_func=notice)
app.add_url_rule(
    "/security/notices/<notice_id>", view_func=update_notice, methods=["PUT"]
)
app.add_url_rule(
    "/security/notices/<notice_id>",
    view_func=delete_notice,
    methods=["DELETE"],
)

app.add_url_rule("/security/notices/<feed_type>.xml", view_func=notices_feed)

app.add_url_rule(
    "/security/releases", view_func=create_release, methods=["POST"]
)
app.add_url_rule(
    "/security/releases/<codename>",
    view_func=delete_release,
    methods=["DELETE"],
)

# cve section
app.add_url_rule("/security/cve", view_func=cve_index)
app.add_url_rule("/security/cve", view_func=bulk_upsert_cve, methods=["PUT"])

app.add_url_rule(
    r"/security/<regex('(cve-|CVE-)\d{4}-\d{4,7}'):cve_id>", view_func=cve
)
app.add_url_rule(
    r"/security/<regex('(cve-|CVE-)\d{4}-\d{4,7}'):cve_id>",
    view_func=delete_cve,
    methods=["DELETE"],
)

# Login
app.add_url_rule("/login", methods=["GET", "POST"], view_func=login_handler)
app.add_url_rule("/logout", view_func=logout)

# Engage pages and takeovers from Discourse
# This section needs to provide takeover data for /

engage_path = "/engage"
engage_pages = EngagePages(
    parser=EngageParser(
        api=DiscourseAPI(
            base_url="https://discourse.ubuntu.com/",
            session=session,
        ),
        index_topic_id=17229,
        url_prefix=engage_path,
    ),
    document_template="/engage/base.html",
    url_prefix=engage_path,
    blueprint_name="engage-pages",
)

app.add_url_rule(engage_path, view_func=build_engage_index(engage_pages))


def build_takeovers(engage_pages):
    def index_page():
        engage_pages.parser.parse()

        # Show only active
        active_takeovers = [
            takeover
            for takeover in engage_pages.parser.takeovers
            if takeover["active"] == "true"
        ]
        return flask.render_template("index.html", takeovers=active_takeovers)

    return index_page


def build_takeovers_index(engage_pages):
    def takeover_index():
        engage_pages.parser.parse()
        sorted_takeovers = sorted(
            engage_pages.parser.takeovers,
            key=lambda takeover: takeover["publish_date"],
            reverse=True,
        )
        active_takeovers = [
            takeover
            for takeover in engage_pages.parser.takeovers
            if takeover["active"] == "true"
        ]
        active_count = len(active_takeovers)
        hidden_count = len(sorted_takeovers) - active_count
        return flask.render_template(
            "takeovers/index.html",
            active_count=active_count,
            hidden_count=hidden_count,
            takeovers=sorted_takeovers,
        )

    return takeover_index


app.add_url_rule("/", view_func=build_takeovers(engage_pages))
app.add_url_rule("/takeovers", view_func=build_takeovers_index(engage_pages))
engage_pages.init_app(app)

# All other routes
template_finder_view = TemplateFinder.as_view("template_finder")
app.add_url_rule("/", view_func=template_finder_view)
app.add_url_rule("/snaps", view_func=search_snaps)
app.add_url_rule("/core/build", view_func=build)
app.add_url_rule("/core/build", view_func=post_build, methods=["POST"])
app.add_url_rule(
    "/core/build/notify", view_func=notify_build, methods=["POST"]
)
app.add_url_rule("/<path:subpath>", view_func=template_finder_view)

url_prefix = "/server/docs"
server_docs = Docs(
    parser=DocParser(
        api=discourse_api,
        category_id=26,
        index_topic_id=11322,
        url_prefix=url_prefix,
    ),
    document_template="/templates/docs/discourse.html",
    url_prefix=url_prefix,
)
server_docs.init_app(app)

# Allow templates to be queried from discourse.ubuntu.com
app.add_url_rule(
    "/templates/<filename>",
    "templates",
    lambda filename: (
        flask.render_template(f"templates/{filename}.html"),
        {"Access-Control-Allow-Origin": "*"},
    ),
)

tutorials_path = "/tutorials"
tutorials_docs = Docs(
    parser=DocParser(
        api=discourse_api,
        category_id=34,
        index_topic_id=13611,
        url_prefix=tutorials_path,
    ),
    document_template="/tutorials/tutorial.html",
    url_prefix=tutorials_path,
    blueprint_name="tutorials",
)
app.add_url_rule(
    tutorials_path, view_func=build_tutorials_index(tutorials_docs)
)
tutorials_docs.init_app(app)

# Ceph docs
ceph_docs = Docs(
    parser=DocParser(
        api=discourse_api, index_topic_id=17250, url_prefix="/ceph/docs"
    ),
    document_template="/templates/docs/discourse.html",
    url_prefix="/ceph/docs",
    blueprint_name="ceph",
)
ceph_docs.init_app(app)

app.add_url_rule(
    "/engage/<page>/thank-you",
    defaults={"language": None},
    view_func=engage_thank_you(engage_pages),
)
app.add_url_rule(
    "/engage/<language>/<page>/thank-you",
    endpoint="alternative_thank-you",
    view_func=engage_thank_you(engage_pages),
)


@app.after_request
def cache_headers(response):
    """
    Set cache expiry to 60 seconds for homepage and blog page
    """

    if flask.request.path in ["/core/build", "/advantage"]:
        response.cache_control.private = True

    if flask.request.path in ["/", "/blog"]:
        response.headers[
            "Cache-Control"
        ] = "max-age=61, stale-while-revalidate=90"

    return response


@app.teardown_appcontext
def remove_db_session(response):
    db_session.remove()
    return response
