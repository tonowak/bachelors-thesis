use clap::{Parser, ValueEnum};
use std::io::Write;
use std::collections::BTreeMap;

#[derive(ValueEnum, Debug, Clone)]
enum QueryType {
    Enum,
    Struct,
}

#[derive(Parser, Debug, Clone)]
// #[command(author)]
struct Args {
    #[arg(short, long)]
    name: String,

    #[arg(short, long)]
    version: String,

    #[arg(short, long)]
    importable_path: String,

    #[arg(value_enum, short, long)]
    query_type: QueryType,
}

fn create_tmp_manifest(crate_name: &str, version: &str) {
    let mut file = std::fs::File::create("tmp_crate/Cargo.toml").unwrap();
    file.write_all(format!("[package]\nname = \"baseline\"\nversion = \"0.1.0\"\nedition = \"2021\"\n[dependencies]\n{crate_name} = \"={version}\"\n").as_bytes()).unwrap();
}

fn get_rustdoc_path(crate_name: &str) -> String {
    let mut cmd = std::process::Command::new("cargo");
    cmd.env("RUSTC_BOOTSTRAP", "1")
        .env(
            "RUSTDOCFLAGS",
            "-Z unstable-options --document-private-items --document-hidden-items --output-format=json --cap-lints allow",
        )
        .stdout(std::process::Stdio::null()) // Don't pollute output
        // .stderr(std::io::stderr)
        .arg("doc")
        .arg("--manifest-path")
        .arg("tmp_crate/Cargo.toml");
    let output = cmd.output().unwrap();
    if !output.status.success() {
        panic!("Failed when running cargo-doc");
    }
    let crate_name = crate_name.replace("-", "_");
    format!("tmp_crate/target/doc/{crate_name}.json")
}

static ENUM_QUERY: &'static str = "
query {
  Crate {
    item {
      ... on Enum {
        name # @output
        variant @fold {
          variants: name @output
        }
        importable_path {
          path @filter(op: \"=\", value: [\"$importable_path\"])
        }
      }
    }
  }
}
";

static STRUCT_QUERY: &'static str = "
query {
  Crate {
    item {
      ... on Struct {
        name # @output
        field @fold {
          fields: name @output
        }
        importable_path {
          path @filter(op: \"=\", value: [\"$importable_path\"])
        }
      }
    }
  }
}
";

fn main() {
    let args = Args::parse();

    let crate_name = &args.name;
    let version = &args.version;
    let importable_path = &args.importable_path;
    let mut importable_path: Vec<&str> = importable_path.split("::").collect();
    // let item_name = importable_path.last().unwrap().clone();
    /*
    match args.query_type {
        | QueryType::Enum => { importable_path.pop(); },
        | QueryType::Struct => {},
    };
    */
    // println!("{:?} {:?}", item_name, importable_path);
    create_tmp_manifest(crate_name, version);
    let rustdoc_path = get_rustdoc_path(crate_name);
    let rustdoc_path = std::path::Path::new(&rustdoc_path);
    let rustdoc = trustfall_rustdoc::load_rustdoc(rustdoc_path).unwrap();
    let rustdoc = trustfall_rustdoc::VersionedIndexedCrate::new(&rustdoc);
    let rustdoc = trustfall_rustdoc::VersionedRustdocAdapter::new(&rustdoc, None).unwrap();
    let mut vars: BTreeMap<String, trustfall::FieldValue> = BTreeMap::new();
    vars.insert("importable_path".to_string(), importable_path.into());
    // vars.insert("item_name".to_string(), item_name.to_string().into());
    let query = match args.query_type {
        | QueryType::Enum => ENUM_QUERY,
        | QueryType::Struct => STRUCT_QUERY,
    };
    let results = rustdoc.run_query(query, vars).unwrap();
    let results: Vec<_> = results.collect();
    // println!("{:?}", results);
    // assert!(results.len() == 1);
    let results = results.first().unwrap();
    let results = results.get(match args.query_type { | QueryType::Enum => "variants", | QueryType::Struct => "fields",}).unwrap();
    let results = match results {
        | trustfall::FieldValue::List(x) => { x }
        | _ => unreachable!()
    };
    let results: Vec<String> = results.into_iter().map(|x| match x {
        | trustfall::FieldValue::String(x) => { x.clone() }
        | _ => unreachable!()
    }).collect();
    println!("{}", results.join(", "));
}
