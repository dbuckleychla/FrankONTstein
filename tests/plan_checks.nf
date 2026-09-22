workflow {
    new groovy.lang.GroovyShell().evaluate(new File("${launchDir}/tests/plan.groovy"))
}
