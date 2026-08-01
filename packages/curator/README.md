# EMBED Agent Context Curator

This companion distribution supplies the optional loopback-only catalog
curation viewer for
[EMBED Agent Context](https://github.com/beatrice-b-m/embedv2-agent-context).
It is versioned in lockstep with the core distribution and is normally
installed through the core package's `curator` extra:

```bash
uv tool install 'embedv2-agent-context[curator]'
```

The package owns the viewer's Python implementation and browser assets. The
core distribution retains the `embed-context curate` command as a lightweight
integration stub and reports an installation hint when this companion is not
present.

The viewer reads only catalog metadata. It must not inspect clinical rows,
identifiers, dates, values, report text, statistics, distributions, or counts.
