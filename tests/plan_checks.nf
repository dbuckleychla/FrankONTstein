workflow {
    new GroovyShell(this.class.classLoader).evaluate(new File("${launchDir}/tests/plan.groovy"))
}
