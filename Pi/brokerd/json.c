/*
 * Just enough JSON for the broker's inbound commands: one flat object of
 * string / number / bool / null values.  Nested values are skipped (typed
 * JV_OTHER).  Anything malformed is rejected as a whole.
 */

#include "brokerd.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *skip_ws(const char *p)
{
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') {
        p++;
    }
    return p;
}

/* Parse a string literal at p (which points at '"').  Copies up to cap-1
 * bytes into out (non-ASCII \u escapes become '?').  Returns the char after
 * the closing quote, or NULL. */
static const char *parse_str(const char *p, char *out, size_t cap)
{
    size_t n = 0;
    p++;
    for (;;) {
        char c = *p++;
        if (c == '\0') {
            return NULL;
        }
        if (c == '"') {
            break;
        }
        if ((unsigned char)c < 0x20) {
            return NULL;
        }
        if (c == '\\') {
            char e = *p++;
            switch (e) {
                case '"': case '\\': case '/': c = e; break;
                case 'b': c = '\b'; break;
                case 'f': c = '\f'; break;
                case 'n': c = '\n'; break;
                case 'r': c = '\r'; break;
                case 't': c = '\t'; break;
                case 'u': {
                    unsigned v = 0;
                    for (int k = 0; k < 4; k++) {
                        char h = *p++;
                        v <<= 4;
                        if (h >= '0' && h <= '9')      v |= (unsigned)(h - '0');
                        else if (h >= 'a' && h <= 'f') v |= (unsigned)(h - 'a' + 10);
                        else if (h >= 'A' && h <= 'F') v |= (unsigned)(h - 'A' + 10);
                        else return NULL;
                    }
                    c = (v < 0x80) ? (char)v : '?';
                    break;
                }
                default: return NULL;
            }
        }
        if (n + 1 < cap) {
            out[n++] = c;
        }
    }
    if (cap) {
        out[n] = '\0';
    }
    return p;
}

/* Skip a nested object/array starting at p.  Returns the char after it. */
static const char *skip_nested(const char *p)
{
    int depth = 0;
    char tmp[1];
    do {
        if (*p == '"') {
            p = parse_str(p, tmp, 0);
            if (p == NULL) {
                return NULL;
            }
            continue;
        }
        if (*p == '{' || *p == '[') depth++;
        else if (*p == '}' || *p == ']') depth--;
        else if (*p == '\0') return NULL;
        p++;
    } while (depth > 0);
    return p;
}

bool json_parse_object(const char *s, JsonObj *out)
{
    out->n = 0;
    const char *p = skip_ws(s);
    if (*p++ != '{') {
        return false;
    }
    p = skip_ws(p);
    if (*p == '}') {
        return *skip_ws(p + 1) == '\0';
    }
    for (;;) {
        JsonField scratch, *f = (out->n < 16) ? &out->f[out->n] : &scratch;
        memset(f, 0, sizeof *f);
        char key[64];

        p = skip_ws(p);
        if (*p != '"' || (p = parse_str(p, key, sizeof key)) == NULL) {
            return false;
        }
        if (strlen(key) < sizeof f->key) {
            strcpy(f->key, key);        /* overlong keys never match */
        }
        p = skip_ws(p);
        if (*p++ != ':') {
            return false;
        }
        p = skip_ws(p);

        if (*p == '"') {
            f->type = JV_STR;
            p = parse_str(p, f->str, sizeof f->str);
        } else if (*p == '{' || *p == '[') {
            f->type = JV_OTHER;
            p = skip_nested(p);
        } else if (strncmp(p, "true", 4) == 0) {
            f->type = JV_BOOL; f->num = 1; p += 4;
        } else if (strncmp(p, "false", 5) == 0) {
            f->type = JV_BOOL; f->num = 0; p += 5;
        } else if (strncmp(p, "null", 4) == 0) {
            f->type = JV_NULL; p += 4;
        } else if (*p == '-' || (*p >= '0' && *p <= '9')) {
            char *end;
            f->type = JV_NUM;
            f->num = strtod(p, &end);
            p = (end == p) ? NULL : end;
        } else {
            return false;
        }
        if (p == NULL) {
            return false;
        }
        if (f != &scratch) {
            out->n++;
        }

        p = skip_ws(p);
        if (*p == ',') {
            p++;
            continue;
        }
        if (*p == '}') {
            return *skip_ws(p + 1) == '\0';
        }
        return false;
    }
}

const JsonField *json_get(const JsonObj *o, const char *key)
{
    for (int i = 0; i < o->n; i++) {
        if (strcmp(o->f[i].key, key) == 0) {
            return &o->f[i];
        }
    }
    return NULL;
}

bool json_as_int(const JsonField *f, long long *out)
{
    if (f == NULL) {
        return false;
    }
    switch (f->type) {
        case JV_NUM:
        case JV_BOOL:
            if (!isfinite(f->num) || fabs(f->num) > 9.0e18) {
                return false;
            }
            *out = (long long)f->num;       /* truncates, like int() */
            return true;
        case JV_STR: {
            const char *p = f->str;
            while (*p == ' ') p++;
            if (*p == '\0') {
                return false;
            }
            char *end;
            long long v = strtoll(p, &end, 10);
            while (*end == ' ') end++;
            if (*end != '\0') {
                return false;
            }
            *out = v;
            return true;
        }
        default:
            return false;
    }
}

void json_put_str(char *dst, size_t cap, const char *s)
{
    size_t n = strlen(dst);
    if (n + 1 >= cap) {
        return;
    }
    dst[n++] = '"';
    for (; *s && n + 8 < cap; s++) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') {
            dst[n++] = '\\';
            dst[n++] = (char)c;
        } else if (c < 0x20) {
            n += (size_t)snprintf(dst + n, cap - n, "\\u%04x", c);
        } else {
            dst[n++] = (char)c;
        }
    }
    if (n + 1 < cap) {
        dst[n++] = '"';
    }
    dst[n] = '\0';
}
