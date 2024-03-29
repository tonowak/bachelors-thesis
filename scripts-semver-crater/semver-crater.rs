use clap::Parser;
use itertools::Itertools;
use std::io::Read;
use std::str::FromStr;

#[derive(Parser, Debug)]
#[command(author)]
struct Args {
    #[arg(short, long)]
    name: String,

    #[arg(short, long)]
    baseline: String,

    #[arg(short, long)]
    current: String,
}

fn is_major_bump(prev: &semver::Version, next: &semver::Version) -> bool {
    assert!(prev < next);
    prev.major != next.major
        || (next.major == 0 && prev.minor != next.minor)
        || (next.major == 0 && next.minor == 0)
}

fn is_minor_bump(prev: &semver::Version, next: &semver::Version) -> bool {
    match is_major_bump(prev, next) {
        true => false,
        false => prev.minor != next.minor || next.major == 0,
    }
}

fn save_report<W: std::io::Write>(
    name: &str,
    baseline: &semver::Version,
    current: &semver::Version,
    result: anyhow::Result<(bool, String)>,
    csv_writer: &mut csv::Writer<W>,
) {
    let mut write_record = |short_descr, full_output| {
        csv_writer
            .write_record([
                name,
                &format!("{baseline} -> {current}"),
                short_descr,
                full_output,
            ])
            .unwrap();
    };
    match result {
        Ok((true, output)) => {
            write_record("OK", &output);
        }
        Ok((false, output)) => {
            let prefix = "--- failure ";
            let suffix = ": ";
            for found_match in regex::Regex::new(&format!("{prefix}(\\w*){suffix}"))
                .unwrap()
                .find_iter(&output)
            {
                let triggered_lint = found_match
                    .as_str()
                    .strip_prefix(prefix)
                    .unwrap()
                    .strip_suffix(suffix)
                    .unwrap();
                write_record(triggered_lint, &output);
            }
        }
        Err(e) => {
            write_record("compile error", &format!("{e:?}"));
        }
    }
}

fn run_on_releases(
    name: &str,
    baseline: &semver::Version,
    current: &semver::Version,
) -> anyhow::Result<(bool, String)> {
    println!("comparing {name}: {baseline} -> {current}");
    // Capturing stderr's output (to parse it manually later), because currently
    // the tool's reports dont't contain enough data needed for semver-crater.
    // This method works only on linux.
    let mut buf_stdout = gag::BufferRedirect::stdout().unwrap();
    let mut buf_stderr = gag::BufferRedirect::stderr().unwrap();

    let report = cargo_semver_checks::Check::new(cargo_semver_checks::Rustdoc::from_registry(
        current.to_string(),
    ))
    .with_baseline(cargo_semver_checks::Rustdoc::from_registry(
        baseline.to_string(),
    ))
    .with_packages(vec![name.to_string()])
    .check_release()?;

    let mut output_stdout = String::new();
    let mut output_stderr = String::new();
    buf_stdout.read_to_string(&mut output_stdout).unwrap();
    buf_stderr.read_to_string(&mut output_stderr).unwrap();
    Ok((report.success(), output_stderr + &output_stdout))
    // Ok((report.success(), "".to_string()))
}

#[allow(dead_code)]
fn run_and_save<W: std::io::Write>(
    name: &str,
    baseline: &semver::Version,
    current: &semver::Version,
    csv_writer: &mut csv::Writer<W>,
) {
    save_report(
        name,
        baseline,
        current,
        run_on_releases(name, baseline, current),
        csv_writer,
    );
}

fn _check_crate(
    versions: Vec<crates_io_api::Version>,
    name: &str,
    csv_writer: &mut csv::Writer<std::fs::File>,
) {
    // Considering only non-yanked non-prereleased versions
    // that have been released since 2017.
    let versions: Vec<semver::Version> = versions
        .into_iter()
        .filter(|v| !v.yanked)
        .filter(|v| v.created_at >= chrono::DateTime::parse_from_rfc3339("2017-01-01T00:00:00+00:00").unwrap())
        .map(|v| semver::Version::parse(&v.num).expect("couldn't parse a version"))
        .filter(|v| v.pre.is_empty())
        .collect();

    // Grouping each version into (major, minor, patch) vectors.
    let mut groups: Vec<Vec<Vec<semver::Version>>> = vec![vec![vec![versions
        .first()
        .expect("version list should be non-empty")
        .clone()]]];
    for (next, prev) in versions.into_iter().tuple_windows() {
        if is_major_bump(&prev, &next) {
            groups.push(vec![vec![prev]]);
        } else if is_minor_bump(&prev, &next) {
            groups.last_mut().unwrap().push(vec![prev]);
        } else {
            groups.last_mut().unwrap().last_mut().unwrap().push(prev);
        }
    }

    for major_group in groups.into_iter() {
        // Comparing versions only in each major group,
        // because the tool doesn't run any lints on major bumps.

        let check_patch_releases =
            |patch_group: &Vec<semver::Version>, csv_writer: &mut csv::Writer<std::fs::File>| {
                if patch_group.len() <= 1 {
                    return;
                }
                let newest = patch_group.first().unwrap();
                let oldest = patch_group.last().unwrap();
                match run_on_releases(name, oldest, newest) {
                    Ok((true, s)) => {
                        // Since comparing the first and last version returned no errors,
                        // there is no need to check versions between them.
                        save_report(name, oldest, newest, Ok((true, s)), csv_writer);
                    }
                    _ => {
                        for (current, baseline) in patch_group.iter().tuple_windows() {
                            run_and_save(name, baseline, current, csv_writer);
                        }
                    }
                }
            };

        check_patch_releases(major_group.first().unwrap(), csv_writer);
        for (previous_patch_group, patch_group) in major_group.iter().tuple_windows() {
            // Comparing two adjacent versions that are a minor bump.
            run_and_save(
                name,
                patch_group.first().unwrap(),
                previous_patch_group.last().unwrap(),
                csv_writer,
            );

            check_patch_releases(patch_group, csv_writer);
        }
    }
}

fn get_crates(client: &crates_io_api::SyncClient, query: crates_io_api::CratesQuery) -> Vec<crates_io_api::Crate> {
    match client.crates(query.clone()) {
        Ok(page) => page.crates,
        _ => {
            println!("failed to get crates, probably because of network issues");
            get_crates(client, query)
        },
    }
}

fn get_versions(client: &crates_io_api::SyncClient, name: &str) -> Vec<crates_io_api::Version> {
    match client.get_crate(name) {
        Ok(crate_) => crate_.versions,
        _ => {
            println!("failed to get versions, probably because of network issues");
            get_versions(client, name)
        },
    }
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    let writer_file = std::fs::File::create("full_report.csv")?;
    let mut csv_writer = csv::Writer::from_writer(writer_file);

    let _client = crates_io_api::SyncClient::new(
        // The format of the string and the duration
        // is documented in https://crates.io/policies#crawlers
        "crates_io_api: cargo-semver-checks (https://github.com/obi1kenobi/cargo-semver-checks/)",
        std::time::Duration::from_millis(1000),
    )?;

    /*
    match args.crates.is_empty() {
        true => {
            for page in 1..101 {
                let mut query = crates_io_api::CratesQuery::builder()
                    .page_size(50)
                    .sort(crates_io_api::Sort::Downloads)
                    .build();
                query.set_page(page);
                if page == 1 {
                    println!("skip {page}");
                }
                else {
                    for crate_info in get_crates(&client, query).into_iter() {
                        let name = crate_info.name;
                        if name == "percent-encoding" || name == "idna" || name == "either" || name == "pin-project-lite" || name == "url" || name == "ppv-lite86" || name == "tokio" || name == "heck" || name == "unicode-width" || name == "slab" || name == "thiserror" || name == "thiserror-impl" || name == "futures" {
                            println!("skip {name}");
                        }
                        else {
                            check_crate(
                                get_versions(&client, &name),
                                &name,
                                &mut csv_writer,
                            );
                            csv_writer.flush()?;
                        }
                    }
                }
            }
        }
        false => {
            for crate_name in args.crates {
                check_crate(
                    get_versions(&client, &crate_name),
                    &crate_name,
                    &mut csv_writer,
                );
                csv_writer.flush()?;
            }
        }
    }
    */

    let _ = is_major_bump;
    let _ = is_minor_bump;
    let _ = get_crates;
    let _ = get_versions;

    let baseline = semver::Version::from_str(&args.baseline)?;
    let current = semver::Version::from_str(&args.current)?;

    save_report(
        &args.name,
        &baseline,
        &current,
        run_on_releases(&args.name, &baseline, &current),
        &mut csv_writer,
    );
    csv_writer.flush()?;
    Ok(())
}
