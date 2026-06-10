from http.server import BaseHTTPRequestHandler, HTTPServer
import sqlite3
import os
import urllib.parse

print("LOADING SERVER CODE")
DB_NAME = "database/Movies.db"

def render_page(page_title, content_html):
    """Load base.html and insert title and content."""
    with open("templates/base.html", "r", encoding="utf-8") as f:
        base = f.read()
    base = base.replace("{{PAGE_TITLE}}", page_title)
    base = base.replace("{{PAGE_CONTENT}}", content_html)
    return base

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == "/":
            self.handle_simple_page(
                "Landing Page",
                "templates/2_sample.html"
            )
        elif path == "/summary":
            self.handle_summary_page(
                "People & Injuries Summary",
                "templates/summary.html",
                parsed_path
            )
        elif path == "/2X":
            self.handle_simple_page(
                "2X Page",
                "templates/2_X.html"
            )
        elif path.startswith("/static/"):
            self.handle_static(path)
        else:
            self.send_error(404, "Not found")

    def handle_simple_page(self, title, template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            content_html = f.read()
        full_html = render_page(title, content_html)
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(full_html.encode("utf-8"))

    def handle_movies_page(self, title, template_path):
        # 1. Get data from database
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT mvtitle, YrMde, mvType FROM Movie LIMIT 10;")
        rows = cur.fetchall()
        conn.close()

        # 2. Build HTML table rows as a string
        table_rows_html = ""
        for row in rows:
            movie_title, release_year, movie_type = row
            table_rows_html += f"""
            <tr>
                <td>{movie_title}</td>
                <td>{release_year}</td>
                <td>{movie_type}</td>
            </tr>
            """

        # 3. Load the template and replace the placeholder
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()

        html = html.replace("{{TABLE_ROWS}}", table_rows_html)
        # 4. Wrap with base.html
        full_html = render_page(title, html)

        # 5. Send response
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(full_html.encode("utf-8"))
    
    def handle_explore_page(self, title, template_path, parsed_path):
        # 1. Read form inputs from the URL (query string)
        query_params = urllib.parse.parse_qs(parsed_path.query)

        # Each value in query_params is a list, e.g. {"program": ["Computer Science"]}
        dir_name = query_params.get("name", [""])[0].strip()
        genre = query_params.get("type", [""])[0].strip()

        # 2. Build SQL query with optional filters
        sql = "SELECT m.mvtitle, d.dirname, m.YrMde, m.mvType FROM Movie m JOIN Director d ON m.dirNumb = d.dirNumb"
        conditions = []
        values = []

        if dir_name:
            conditions.append("d.DIRNAME LIKE ?")
            values.append("%" + dir_name + "%")  # contains text

        if genre:
            try:
                "#"
                conditions.append("m.MVTYPE LIKE ?")
                values.append("%" + genre + "%")
            except ValueError:
                # If user types something not a number, ignore injured filter
                pass

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        # 3. Run the query
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute(sql, values)
        rows = cur.fetchall()
        conn.close()

        # 4. Build table rows HTML
        table_rows_html = ""
        for movie_title, director, release_year, movie_type in rows:
            table_rows_html += f"""
            <tr>
                <td>{movie_title}</td>
                <td>{director}</td>
                <td>{release_year}</td>
                <td>{movie_type}</td>
            </tr>
            """

        # If no results, show a friendly message
        if not rows:
            table_rows_html = """
            <tr>
                <td colspan="4">No movies match your filter.</td>
            </tr>
            """
        # 5. Build a simple “You searched for …” summary
        if not dir_name and not genre:
            filter_summary = "Showing all movies (no filter applied)."
        else:
            parts = []
            if dir_name:
                parts.append(f"director contains \"{dir_name}\"")
            if genre:
                parts.append(f"genre contains \"{genre}\"")
            filter_summary = "You searched for: " + " and ".join(parts) + "."
        # 6. Load movies.html and insert the summary table rows
        with open(template_path, "r", encoding="utf-8") as f:
            filter_movies_template = f.read()
        movies_page_html = (
            filter_movies_template
            .replace("{{TABLE_ROWS}}", table_rows_html)
            .replace("{{FILTER_SUMMARY}}", filter_summary)
        )

        # 7. Wrap with base.html
        full_html = render_page(title, movies_page_html)

        # 8. Send response
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(full_html.encode("utf-8"))

    def handle_summary_page(
        self,
        title,
        template_path,
        parsed_path
    ):

        query_params = urllib.parse.parse_qs(
            parsed_path.query
        )

        injury_filter = query_params.get(
            "injury",
            [""]
        )[0]

        ejected_filter = query_params.get(
            "ejected",
            [""]
        )[0]

        year_filter = query_params.get(
            "year",
            [""]
        )[0]

        conn = sqlite3.connect(
            "database/Road_Accidents.db"
        )

        cur = conn.cursor()

        cur.execute("""
            SELECT
                INJ_LEVEL,
                INJ_LEVEL_DESC
            FROM Injury
            ORDER BY INJ_LEVEL_DESC
        """)

        injuries = cur.fetchall()

        injury_options = ""

        for code, desc in injuries:
            injury_options += (
                f'<option value="{code}">'
                f'{desc}'
                f'</option>'
            )

        sql = """
            SELECT
                i.INJ_LEVEL_DESC,
                COUNT(*)
            FROM Person p
            JOIN Injury i
                ON p.INJ_LEVEL = i.INJ_LEVEL
            JOIN Accident a
                ON p.ACCIDENT_NO = a.ACCIDENT_NO
        """

        conditions = []
        values = []

        if injury_filter:
            conditions.append(
                "p.INJ_LEVEL = ?"
            )
            values.append(injury_filter)

        if ejected_filter:
            conditions.append(
                "p.EJECTED_CODE = ?"
            )
            values.append(ejected_filter)

        if year_filter:
            conditions.append(
                "strftime('%Y', a.ACCIDENT_DATE) = ?"
            )
            values.append(year_filter)

        if conditions:
            sql += (
                " WHERE " +
                " AND ".join(conditions)
            )

        sql += """
            GROUP BY i.INJ_LEVEL_DESC
            ORDER BY COUNT(*) DESC
        """

        cur.execute(sql, values)

        rows = cur.fetchall()

        table_rows = ""

        for injury, total in rows:
            table_rows += f"""
            <tr>
                <td>{injury}</td>
                <td>{int(total):,}</td>
            </tr>
            """

        cur.execute("""
            SELECT COUNT(*)
            FROM Person
            WHERE EJECTED_CODE != 0
        """)

        total_ejected = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM Person
            WHERE TAKEN_HOSPITAL = 'Y'
        """)

        total_hospital = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM Person
            WHERE INJ_LEVEL = 2
        """)

        total_serious = cur.fetchone()[0]

        conn.close()

        with open(
            template_path,
            "r",
            encoding="utf-8"
        ) as f:

            html = f.read()

        print(total_ejected)
        print(total_hospital)
        print(total_serious)

        html = (
            html
            .replace(
                "{{INJURY_OPTIONS}}",
                injury_options
            )
            .replace(
                "{{TABLE_ROWS}}",
                table_rows
            )
            .replace(
                "{{TOTAL_EJECTED}}",
                f"{total_ejected:,}"
            )
            .replace(
                "{{TOTAL_HOSPITAL}}",
                f"{total_hospital:,}"
            )
            .replace(
                "{{TOTAL_SERIOUS}}",
                f"{total_serious:,}"
            )
        )

        full_html = render_page(
            title,
            html
        )

        self.send_response(200)
        self.send_header(
            "Content-type",
            "text/html; charset=utf-8"
        )
        self.end_headers()

        self.wfile.write(
            full_html.encode("utf-8")
        )

    def handle_static(self, path):
        # e.g. /static/style.css
        file_path = path.lstrip("/")  # remove leading '/'
        if os.path.isfile(file_path):
            if file_path.endswith(".css"):
                content_type = "text/css"
            else:
                content_type = "application/octet-stream"

            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-type", content_type)
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, "Static file not found")



def run():
    server_address = ("", 8000)  # localhost:8000
    httpd = HTTPServer(server_address, RequestHandler)
    print("Server running at http://localhost:8000")
    httpd.serve_forever()


if __name__ == "__main__":
    run()